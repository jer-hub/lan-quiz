# Optional AI Quiz Generator

AI is **not required** for hosting or playing. Live games stay on the LAN.

## Overview

Teachers open **New / Edit quiz** → **AI Quiz Generator (Free tier supported)**:

1. Optional: upload a lesson file (PDF, DOCX, TXT, MD) → text extracted **on the LanQuiz server**
2. Edit topic + source material
3. Paste a personal API key (Google AI Studio recommended)
4. Generate → review/edit questions → Save

## Defaults

| Setting | Value |
|---------|--------|
| Provider | Google AI Studio (Gemini) |
| Model | `gemini-3.8-flash` |
| Alternates | `gemini-3.5-flash-lite` (fast, low cost), `gemini-4-argon` (most capable) |
| Also | Groq, OpenAI, OpenRouter, custom OpenAI-compatible base URL |

Get a Gemini key: https://aistudio.google.com/apikey

LanQuiz calls Gemini through Google's OpenAI-compatible endpoint
(`https://generativelanguage.googleapis.com/v1beta/openai`), with the key sent as a bearer token.

## Privacy and keys

- Keys stay in the **browser** (`localStorage` if “Remember on this device”).
- LanQuiz **never** stores API keys in SQLite.
- Uploaded files are read in memory for extract, then discarded. Only extracted text is sent to the AI provider with the prompt.

## File extract limits

| Limit | Value |
|-------|--------|
| Formats | `.pdf` `.docx` `.txt` `.md` |
| Max upload | 5 MB |
| Max text kept | ~24,000 characters (~6K tokens; fits free-tier TPM headroom) |
| OCR | **No** — scanned/image-only PDFs will fail; use text PDFs or paste notes |

## Provider notes

- **Google AI Studio:** Gemini 3 models always think, and thinking counts against the output limit, so LanQuiz asks for low reasoning effort and allows up to 8,192 output tokens. JSON mode is not requested; the quiz JSON is read from the reply.
- **Groq:** no general “upload file to Groq” API for prompting; LanQuiz extracts text locally first.
- Free tiers enforce RPM / TPM / TPD — large materials may need trimming.
- Rate-limit warnings surface in the UI; HTTP 429 returns a clear message.

## Related endpoints

- `GET /api/ai/presets`
- `POST /api/ai/extract-text`
- `POST /api/ai/generate-quiz`

See [API.md](API.md).
