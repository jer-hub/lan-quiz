"""Optional AI quiz generation (teacher-only cloud proxy)."""

from __future__ import annotations

import json
import logging
import random
import re
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, model_validator

from app.auth import require_teacher
from app.models import User
from app.schemas import QuestionCreate, QuizCreate
from app.text_extract import MAX_EXTRACT_CHARS, MAX_UPLOAD_BYTES, extract_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "google": {
        "id": "google",
        "label": "Google AI Studio (Gemini)",
        "base_url": GEMINI_BASE_URL,
        "docs_url": "https://aistudio.google.com/apikey",
        "models": [
            {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash (default)", "aliases": []},
            {"id": "gemini-3.5-flash-lite", "label": "Gemini 3.5 Flash-Lite (fast, low cost)", "aliases": []},
            {"id": "gemini-4-argon", "label": "Gemini 4 Argon (most capable)", "aliases": []},
        ],
        "default_model": "gemini-3.8-flash",
    },
}

# A healthy quiz generation takes about 4-18 s. A model under heavy demand can answer 503
# or hold the request without replying, so each attempt is capped and a busy or slow
# model falls back once to Flash-Lite.
PROVIDER_TIMEOUT = httpx.Timeout(45.0, connect=10.0)
FALLBACK_MODEL = "gemini-3.5-flash-lite"
BUSY_MESSAGE = "Gemini is busy right now (high demand). Please try again in a minute."

RATE_WARN_THRESHOLD = 5

DEFAULT_PROVIDER = "google"
DEFAULT_MODEL = PROVIDER_PRESETS[DEFAULT_PROVIDER]["default_model"]


class AiGenerateRequest(BaseModel):
    provider: str = Field(default=DEFAULT_PROVIDER)
    model: str = Field(default=DEFAULT_MODEL, min_length=1, max_length=200)
    api_key: str = Field(..., min_length=8, max_length=500)
    topic: str = Field(default="", max_length=2000)
    source_material: str | None = Field(default=None, max_length=MAX_EXTRACT_CHARS)
    question_count: int = Field(default=8, ge=3, le=20)
    difficulty: str = Field(default="medium", max_length=40)
    language: str = Field(default="English", max_length=60)

    @model_validator(mode="after")
    def require_topic_or_material(self) -> AiGenerateRequest:
        topic = (self.topic or "").strip()
        material = (self.source_material or "").strip()
        if len(topic) < 3 and len(material) < 20:
            raise ValueError("Provide a topic (3+ chars) and/or source material (20+ chars)")
        self.topic = topic
        self.source_material = material or None
        return self


class RateLimitInfo(BaseModel):
    warning: bool = False
    message: str = ""
    remaining_requests: int | None = None
    retry_after_seconds: int | None = None


class AiGenerateResponse(BaseModel):
    quiz: QuizCreate
    rate_limit: RateLimitInfo
    model_used: str
    fallback_used: bool = False


class AiExtractResponse(BaseModel):
    text: str
    char_count: int
    truncated: bool
    warning: str
    filename: str


def _build_prompt(
    topic: str,
    question_count: int,
    difficulty: str,
    language: str,
    source_material: str | None = None,
) -> list[dict[str, str]]:
    system = (
        "You are a quiz author for LanQuiz, a classroom Kahoot-style app. "
        "Return ONLY valid JSON (no markdown) matching this schema:\n"
        "{\n"
        '  "title": string,\n'
        '  "description": string,\n'
        '  "questions": [\n'
        "    {\n"
        '      "text": string,\n'
        '      "options": string[2..6],\n'
        '      "correct_indices": int[] (0-based, at least one),\n'
        '      "time_limit": int (5..120, prefer 15-25),\n'
        '      "image": null\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Rules: age-appropriate; unambiguous; one clear best answer unless multi-correct; "
        "options non-empty and distinct; no answer keys in the question text. "
        "Vary correct_indices across the quiz — do not put the correct option at index 0 "
        "for every question; spread correct answers across different option positions."
    )
    if source_material:
        system += (
            " When source material is provided, base every question only on that material; "
            "do not invent facts outside it. Prefer the teacher's topic as quiz focus/title intent."
        )
        focus = topic if topic else "the provided source material"
        user = (
            f"Create a {difficulty} quiz in {language} focused on: {focus}\n"
            f"Exactly {question_count} questions.\n\n"
            f"Source material:\n{source_material}"
        )
    else:
        user = (
            f"Create a {difficulty} quiz in {language} about: {topic}\n"
            f"Exactly {question_count} questions."
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise HTTPException(status_code=502, detail="AI returned non-JSON content")
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=502, detail="AI returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="AI JSON root must be an object")
    return data


def _shuffle_options(
    options: list[str], correct_indices: list[int]
) -> tuple[list[str], list[int]]:
    """Randomize option order so correct answers are not stuck on A."""
    from app.utils.shuffle import shuffle_options

    shuffled, new_correct, _ = shuffle_options(options, correct_indices)
    return shuffled, new_correct


def _validate_quiz(data: dict[str, Any], expected_count: int) -> QuizCreate:
    title = str(data.get("title") or "AI Quiz").strip()[:200] or "AI Quiz"
    description = str(data.get("description") or "").strip()[:2000]
    raw_questions = data.get("questions")
    if not isinstance(raw_questions, list) or not raw_questions:
        raise HTTPException(status_code=502, detail="AI returned no questions")

    questions: list[QuestionCreate] = []
    for item in raw_questions[:expected_count]:
        if not isinstance(item, dict):
            continue
        options = item.get("options") or []
        if not isinstance(options, list):
            continue
        options = [str(o).strip() for o in options if str(o).strip()]
        if len(options) < 2:
            continue
        options = options[:6]
        correct = item.get("correct_indices") or [0]
        if not isinstance(correct, list):
            correct = [0]
        correct_indices = sorted(
            {int(c) for c in correct if isinstance(c, (int, float, str)) and str(c).lstrip("-").isdigit()}
        )
        correct_indices = [c for c in correct_indices if 0 <= c < len(options)]
        if not correct_indices:
            correct_indices = [0]
        options, correct_indices = _shuffle_options(options, correct_indices)
        try:
            time_limit = int(item.get("time_limit") or 20)
        except (TypeError, ValueError):
            time_limit = 20
        time_limit = max(5, min(120, time_limit))
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        questions.append(
            QuestionCreate(
                text=text[:2000],
                image=None,
                options=options,
                correct_indices=correct_indices,
                time_limit=time_limit,
            )
        )

    if len(questions) < 3:
        raise HTTPException(
            status_code=502,
            detail="AI returned too few valid questions. Try again or adjust the topic.",
        )
    return QuizCreate(title=title, description=description, questions=questions)


def _parse_rate_limit(headers: httpx.Headers) -> RateLimitInfo:
    remaining: int | None = None
    for key in (
        "x-ratelimit-remaining-requests",
        "x-ratelimit-remaining",
        "x-ratelimit-remaining-tokens",
    ):
        raw = headers.get(key)
        if raw is None:
            continue
        try:
            remaining = int(float(raw))
            if "token" not in key.lower() or remaining is not None:
                # Prefer request remaining when available
                if "request" in key.lower() or key == "x-ratelimit-remaining":
                    break
        except ValueError:
            continue

    retry_after: int | None = None
    ra = headers.get("retry-after")
    if ra:
        try:
            retry_after = int(float(ra))
        except ValueError:
            retry_after = None

    warning = remaining is not None and remaining <= RATE_WARN_THRESHOLD
    message = ""
    if warning:
        message = (
            f"Approaching rate limit: about {remaining} request(s) remaining on this key/tier. "
            "Slow down or wait before generating again."
        )
    return RateLimitInfo(
        warning=warning,
        message=message,
        remaining_requests=remaining,
        retry_after_seconds=retry_after,
    )


def _provider_reason(resp: httpx.Response, api_key: str) -> str:
    """Short provider error message for the server log, with the API key removed."""
    msg = None
    try:
        err = resp.json()
        if isinstance(err, list) and err:
            err = err[0]
        if isinstance(err, dict):
            msg = (err.get("error") or {}).get("message")
    except Exception:
        msg = None
    text = str(msg or resp.text or "")[:300]
    return text.replace(api_key, "[key]") if api_key else text


def _provider_error_hint(status_code: int) -> str:
    if status_code in (401, 403):
        return "Google AI Studio rejected the API key. Check the key and that the Gemini API is enabled."
    if status_code == 404:
        return "Google AI Studio does not recognise this model. Pick another model."
    if status_code == 400:
        return "Google AI Studio rejected the request (HTTP 400). Check the API key and model."
    return f"AI provider returned an error (HTTP {status_code})"


@router.get("/presets")
async def ai_presets(_teacher: User = Depends(require_teacher)) -> dict[str, Any]:
    return {
        "label": "AI Quiz Generator (Google AI Studio)",
        "default_provider": DEFAULT_PROVIDER,
        "default_model": DEFAULT_MODEL,
        "providers": list(PROVIDER_PRESETS.values()),
        "note": (
            "Optional cloud feature. Paste your own API key (stored only in this browser). "
            "Upload PDF/DOCX/TXT/MD to extract text on this LAN server; only text is sent to the AI provider. "
            "Live LanQuiz games do not require AI."
        ),
        "extract": {
            "max_upload_bytes": MAX_UPLOAD_BYTES,
            "max_extract_chars": MAX_EXTRACT_CHARS,
            "formats": [".pdf", ".docx", ".txt", ".md"],
        },
    }


@router.post("/extract-text", response_model=AiExtractResponse)
async def extract_text_endpoint(
    file: UploadFile = File(...),
    _teacher: User = Depends(require_teacher),
) -> AiExtractResponse:
    filename = file.filename or "upload"
    # Read with size cap (reject oversized before full buffer if possible)
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)",
            )
        chunks.append(chunk)
    data = b"".join(chunks)
    try:
        result = extract_text(filename, file.content_type, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Text extract failed filename=%s err=%s", filename[:80], type(exc).__name__)
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from this file",
        ) from exc
    finally:
        data = b""
        chunks.clear()
        await file.close()

    return AiExtractResponse(
        text=result.text,
        char_count=result.char_count,
        truncated=result.truncated,
        warning=result.warning,
        filename=result.filename,
    )


@router.post("/generate-quiz", response_model=AiGenerateResponse)
async def generate_quiz(
    payload: AiGenerateRequest,
    _teacher: User = Depends(require_teacher),
) -> AiGenerateResponse:
    provider = payload.provider.strip().lower()
    if provider not in PROVIDER_PRESETS:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {payload.provider}")
    model = payload.model.strip()
    api_key = payload.api_key.strip()

    material = payload.source_material
    if material and len(material) > MAX_EXTRACT_CHARS:
        material = material[:MAX_EXTRACT_CHARS]

    url = f"{GEMINI_BASE_URL}/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": _build_prompt(
            payload.topic,
            payload.question_count,
            payload.difficulty,
            payload.language,
            material,
        ),
        "temperature": 0.4,
        # Thinking counts against the output limit: keep it low and leave room so the
        # quiz JSON is not cut off. json_object mode is not documented for this endpoint.
        "reasoning_effort": "low",
        "max_tokens": 8192,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # The chosen model first; if it is busy (503) or does not answer in time, Flash-Lite once.
    attempts = [model] if model == FALLBACK_MODEL else [model, FALLBACK_MODEL]
    resp: httpx.Response | None = None
    model_used = model
    started = time.monotonic()
    for attempt_model in attempts:
        attempt_body = {**body, "model": attempt_model}
        model_used = attempt_model
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=PROVIDER_TIMEOUT) as client:
                resp = await client.post(url, headers=headers, json=attempt_body)
        except httpx.TimeoutException as exc:
            logger.warning(
                "AI provider timed out model=%s after=%.1fs (%s)",
                attempt_model,
                time.monotonic() - started,
                type(exc).__name__,
            )
            resp = None
            continue
        except httpx.RequestError as exc:
            logger.warning("AI provider request failed model=%s: %s", attempt_model, type(exc).__name__)
            raise HTTPException(
                status_code=502,
                detail="Could not reach AI provider. Check internet access on the LanQuiz host.",
            ) from exc
        if resp.status_code == 503:
            logger.warning(
                "AI provider busy status=503 model=%s after=%.1fs reason=%s",
                attempt_model,
                time.monotonic() - started,
                _provider_reason(resp, api_key),
            )
            resp = None
            continue
        break
    if resp is None:
        raise HTTPException(status_code=503, detail=BUSY_MESSAGE)
    elapsed = time.monotonic() - started

    rate = _parse_rate_limit(resp.headers)

    if resp.status_code == 429:
        detail = {
            "message": "Rate limit exceeded. Wait and try again, or use another key/model.",
            "retry_after_seconds": rate.retry_after_seconds,
        }
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)

    if resp.status_code >= 400:
        # The provider's own message goes to the server log only, with the key removed.
        logger.warning(
            "AI provider returned status=%s model=%s after=%.1fs reason=%s",
            resp.status_code,
            model_used,
            elapsed,
            _provider_reason(resp, api_key),
        )
        raise HTTPException(status_code=502, detail=_provider_error_hint(resp.status_code))

    try:
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=502, detail="Unexpected AI provider response") from exc

    if not isinstance(content, str) or len(content) > 200_000:
        raise HTTPException(status_code=502, detail="AI response too large or empty")

    quiz = _validate_quiz(_extract_json(content), payload.question_count)
    # Trim to requested count if model overshot
    if len(quiz.questions) > payload.question_count:
        quiz = QuizCreate(
            title=quiz.title,
            description=quiz.description,
            questions=quiz.questions[: payload.question_count],
        )

    api_key = ""
    logger.info(
        "AI quiz generated model=%s fallback=%s questions=%s after=%.1fs warning=%s",
        model_used,
        model_used != model,
        len(quiz.questions),
        elapsed,
        rate.warning,
    )
    return AiGenerateResponse(
        quiz=quiz,
        rate_limit=rate,
        model_used=model_used,
        fallback_used=model_used != model,
    )
