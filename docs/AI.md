# Optional AI Quiz Generator

AI is **not required** for hosting or playing. Live games stay on the LAN.

## Overview

Teachers open **New / Edit quiz** → **Generate with AI**:

1. Paste a Google AI Studio API key (saved in the browser if you choose)
2. Give a topic, and optionally a lesson file and/or notes
3. Pick the number of questions, difficulty and language
4. Generate → review/edit questions → Save

## Provider

LanQuiz uses **Google AI Studio (Gemini)** only, through Google's Interactions API
(`https://generativelanguage.googleapis.com/v1beta/interactions`). The key is sent in the
`x-goog-api-key` header.

| Setting | Value |
|---------|--------|
| Model | `gemini-3.8-flash` (default) |
| Alternates | `gemini-3.5-flash-lite` (fast, low cost), `gemini-4-argon` (most capable) |

Get a key: https://aistudio.google.com/apikey

## Lesson files

LanQuiz does **no text conversion**. Files go to Gemini as-is, and Gemini reads them natively.

| File | What happens |
|------|--------------|
| PDF | Sent to Gemini as a document. Gemini reads text, tables, diagrams and charts, and its vision handles scanned pages. |
| PNG, JPEG, WebP | Sent to Gemini as an image (e.g. a photo of a textbook page). |
| TXT, Markdown | Already text: the browser reads it into the notes box, where you can edit it. |
| Word (DOCX) | Not supported by Gemini. Save it as PDF first. |

Limits: one file per draft, up to 10 MB; notes up to 24,000 characters.

## Privacy and keys

- Keys stay in the **browser** (`localStorage` if “Remember on this device”). LanQuiz never stores them and never writes them to the log.
- **An attached file is sent to Google in full**, not just its text. LanQuiz itself does not keep it.
- Requests are sent with `store: false`, so Google does not keep the interaction for later retrieval. Google's own terms for your AI Studio tier still apply to what you send.

## How requests are sent

- Gemini 3 models always think before answering, and thinking counts against the output limit. LanQuiz asks for `thinking_level: "low"` and allows up to 8,192 output tokens. Only the model's final output is read; thoughts are ignored.
- A generation normally takes about 4–18 seconds. Each attempt is capped at 45 seconds (10 seconds to connect).
- If the chosen model is busy (Google answers 503 "high demand") or does not answer within 45 seconds, LanQuiz retries once with `gemini-3.5-flash-lite`, with the same file and notes, and tells the teacher which model wrote the draft. Other errors are not retried.
- Free tiers enforce request and token limits. HTTP 429 returns a clear message.

## Troubleshooting

The server log records every attempt with the model and how long it took, and for errors Google's reason (with the key removed).

| You see | Likely cause |
|---------|--------------|
| Gemini is busy right now | Both the chosen model and Flash-Lite were busy or slow. Google's demand spikes are usually short; try again in a minute. |
| "…was busy, so this draft was written by Gemini 3.5 Flash-Lite" | Not an error: the chosen model was busy, and the fallback worked. |
| Attach a PDF or an image | The file type isn't supported (e.g. Word). Save it as PDF. |
| Google AI Studio rejected the API key | Wrong or revoked key, or the Gemini API is not enabled for the key's project. |
| Google AI Studio does not recognise this model | The model ID is not available to your key. Pick another model. |
| Rejected the request (HTTP 400) | Usually an invalid key or model; the server log has Google's exact reason. |

## Related endpoints

- `GET /api/ai/presets`
- `POST /api/ai/generate-quiz`

See [API.md](API.md).
