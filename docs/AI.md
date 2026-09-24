# Optional AI Quiz Generator

AI is **not required** for hosting or playing. Live games stay on the LAN.

## Overview

Teachers open **New / Edit quiz** → **AI Quiz Generator (Free tier supported)**:

1. Optional: upload a lesson file (PDF, DOCX, TXT, MD) → text extracted **on the LanQuiz server**
2. Edit topic + source material
3. Paste a personal API key (Groq recommended)
4. Generate → review/edit questions → Save

## Defaults

| Setting | Value |
|---------|--------|
| Provider | Groq (free tier supported) |
| Model | `qwen/qwen3-32b` (alias `qwen/qwen3.8-27b`) |
| Alternate | `openai/gpt-oss-120b` |
| Also | OpenAI, OpenRouter, custom OpenAI-compatible base URL |

Get a Groq key: https://console.groq.com/keys

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

- **Groq:** no general “upload file to Groq” API for prompting; LanQuiz extracts text locally first.
- Free tiers enforce RPM / TPM / TPD — large materials may need trimming.
- Rate-limit warnings surface in the UI; HTTP 429 returns a clear message.

## Related endpoints

- `GET /api/ai/presets`
- `POST /api/ai/extract-text`
- `POST /api/ai/generate-quiz`

See [API.md](API.md).
