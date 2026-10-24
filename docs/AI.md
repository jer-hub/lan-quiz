# Optional AI Quiz Generator

AI is **not required** for hosting or playing. Live games stay on the LAN.

## Overview

Teachers open **New / Edit quiz** → **AI Quiz Generator**:

1. Optional: upload a lesson file (PDF, DOCX, TXT, MD) → text extracted **on the LanQuiz server**
2. Edit topic + source material
3. Paste a Google AI Studio API key
4. Generate → review/edit questions → Save

## Provider

LanQuiz uses **Google AI Studio (Gemini)** only.

| Setting | Value |
|---------|--------|
| Model | `gemini-3.8-flash` (default) |
| Alternates | `gemini-3.5-flash-lite` (fast, low cost), `gemini-4-argon` (most capable) |
| Endpoint | `https://generativelanguage.googleapis.com/v1beta/openai` (OpenAI-compatible), key sent as a bearer token |

Get a key: https://aistudio.google.com/apikey

## Privacy and keys

- Keys stay in the **browser** (`localStorage` if “Remember on this device”).
- LanQuiz **never** stores API keys in SQLite and never writes them to the log.
- Uploaded files are read in memory for extract, then discarded. Only extracted text is sent to Google with the prompt.

## File extract limits

| Limit | Value |
|-------|--------|
| Formats | `.pdf` `.docx` `.txt` `.md` |
| Max upload | 5 MB |
| Max text kept | ~24,000 characters (~6K tokens) |
| OCR | **No** — scanned/image-only PDFs will fail; use text PDFs or paste notes |

## How requests are sent

- Gemini 3 models always think before answering, and thinking counts against the output limit. LanQuiz asks for low reasoning effort and allows up to 8,192 output tokens. JSON mode is not requested; the quiz JSON is read from the reply.
- A generation normally takes about 4–18 seconds. Each attempt is capped at 45 seconds (10 seconds to connect).
- If the chosen model is busy (Google answers 503 "high demand") or does not answer within 45 seconds, LanQuiz retries once with `gemini-3.5-flash-lite` and tells the teacher which model wrote the draft. Other errors are not retried.
- Free tiers enforce request and token limits; large materials may need trimming. HTTP 429 returns a clear message.

## Troubleshooting

The server log records every attempt with the model and how long it took, and for errors Google's reason (with the key removed).

| You see | Likely cause |
|---------|--------------|
| Gemini is busy right now | Both the chosen model and Flash-Lite were busy or slow. Google's demand spikes are usually short; try again in a minute. |
| "…was busy, so this draft was written by Gemini 3.5 Flash-Lite" | Not an error: the chosen model was busy, and the fallback worked. |
| Google AI Studio rejected the API key | Wrong or revoked key, or the Gemini API is not enabled for the key's project. |
| Google AI Studio does not recognise this model | The model ID is not available to your key. Pick another model. |
| Rejected the request (HTTP 400) | Usually an invalid key or model; the server log has Google's exact reason. |

## Related endpoints

- `GET /api/ai/presets`
- `POST /api/ai/extract-text`
- `POST /api/ai/generate-quiz`

See [API.md](API.md).
