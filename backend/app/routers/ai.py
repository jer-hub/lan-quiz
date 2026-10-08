"""Optional AI quiz generation (teacher-only cloud proxy)."""

from __future__ import annotations

import json
import logging
import random
import re
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

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "groq": {
        "id": "groq",
        "label": "Groq (free tier supported)",
        "base_url": "https://api.groq.com/openai/v1",
        "docs_url": "https://console.groq.com/keys",
        "models": [
            {
                "id": "qwen/qwen3-32b",
                "label": "Qwen3 32B (default)",
                "aliases": ["qwen/qwen3.8-27b"],
            },
            {
                "id": "openai/gpt-oss-120b",
                "label": "GPT-OSS 120B",
                "aliases": [],
            },
            {"id": "llama-3.3-70b-versatile", "label": "Llama 3.3 70B", "aliases": []},
            {"id": "llama-3.1-8b-instant", "label": "Llama 3.1 8B Instant", "aliases": []},
        ],
        "default_model": "qwen/qwen3-32b",
    },
    "openai": {
        "id": "openai",
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "docs_url": "https://platform.openai.com/api-keys",
        "models": [
            {"id": "gpt-4o-mini", "label": "GPT-4o mini", "aliases": []},
            {"id": "gpt-4o", "label": "GPT-4o", "aliases": []},
        ],
        "default_model": "gpt-4o-mini",
    },
    "openrouter": {
        "id": "openrouter",
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "docs_url": "https://openrouter.ai/keys",
        "models": [
            {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B", "aliases": []},
            {"id": "qwen/qwen3-32b", "label": "Qwen3 32B", "aliases": ["qwen/qwen3.8-27b"]},
        ],
        "default_model": "qwen/qwen3-32b",
    },
    "custom": {
        "id": "custom",
        "label": "Custom (OpenAI-compatible)",
        "base_url": "",
        "docs_url": "",
        "models": [],
        "default_model": "",
    },
}

RATE_WARN_THRESHOLD = 5


class AiGenerateRequest(BaseModel):
    provider: str = Field(default="groq")
    model: str = Field(default="qwen/qwen3-32b", min_length=1, max_length=200)
    api_key: str = Field(..., min_length=8, max_length=500)
    base_url: str | None = Field(default=None, max_length=500)
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


class AiExtractResponse(BaseModel):
    text: str
    char_count: int
    truncated: bool
    warning: str
    filename: str


def _resolve_base_url(provider: str, base_url: str | None) -> str:
    key = provider.strip().lower()
    if key == "custom":
        url = (base_url or "").strip().rstrip("/")
        if not url:
            raise HTTPException(status_code=400, detail="Custom provider requires a base_url")
        return url
    preset = PROVIDER_PRESETS.get(key)
    if not preset:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    return (base_url or preset["base_url"]).strip().rstrip("/")


def _normalize_model(provider: str, model: str) -> str:
    m = model.strip()
    # Map planned alias to current Groq ID
    if m == "qwen/qwen3.8-27b":
        return "qwen/qwen3-32b"
    preset = PROVIDER_PRESETS.get(provider.strip().lower())
    if preset:
        for item in preset.get("models") or []:
            if m in (item.get("aliases") or []):
                return item["id"]
    return m


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


@router.get("/presets")
async def ai_presets(_teacher: User = Depends(require_teacher)) -> dict[str, Any]:
    return {
        "label": "AI Quiz Generator (Free tier supported)",
        "default_provider": "groq",
        "default_model": "qwen/qwen3-32b",
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
    model = _normalize_model(provider, payload.model)
    base_url = _resolve_base_url(provider, payload.base_url)
    api_key = payload.api_key.strip()

    material = payload.source_material
    if material and len(material) > MAX_EXTRACT_CHARS:
        material = material[:MAX_EXTRACT_CHARS]

    url = f"{base_url}/chat/completions"
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
        "max_tokens": 4096,
    }
    # Prefer JSON mode when providers support it
    if provider in ("groq", "openai", "openrouter"):
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://lanquiz.local"
        headers["X-Title"] = "LanQuiz"

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="AI provider timed out") from exc
    except httpx.RequestError as exc:
        logger.warning("AI provider request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not reach AI provider. Check internet access on the LanQuiz host.",
        ) from exc
    finally:
        # Ensure key is not kept beyond this request path
        api_key = ""

    rate = _parse_rate_limit(resp.headers)

    if resp.status_code == 429:
        detail = {
            "message": "Rate limit exceeded. Wait and try again, or use another key/model.",
            "retry_after_seconds": rate.retry_after_seconds,
        }
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)

    if resp.status_code >= 400:
        msg = "AI provider error"
        try:
            err = resp.json()
            msg = (
                err.get("error", {}).get("message")
                or err.get("message")
                or msg
            )
        except Exception:
            msg = resp.text[:300] or msg
        # Never echo the API key
        raise HTTPException(status_code=502, detail=str(msg)[:500])

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

    logger.info(
        "AI quiz generated provider=%s model=%s questions=%s warning=%s",
        provider,
        model,
        len(quiz.questions),
        rate.warning,
    )
    return AiGenerateResponse(quiz=quiz, rate_limit=rate)
