# API reference

Base URL: `http://HOST:8000`  
Auth: `Authorization: Bearer <JWT>` unless noted.

OpenAPI interactive docs (when not overridden by SPA): try `/docs` in development if the SPA catch-all is disabled; production serves the SPA for unknown paths. Prefer this document for classroom use.

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | No | `{ status, app }` |

## Auth

| Method | Path | Auth | Body | Description |
|--------|------|------|------|-------------|
| POST | `/api/auth/register` | No | `{ username, password }` | Create teacher. Closed once a teacher exists, unless `ALLOW_TEACHER_REGISTRATION=true` |
| POST | `/api/auth/login` | No | `{ username, password }` | Teacher JWT |
| POST | `/api/auth/student/login` | No | `{ student_code, password, join_code? }` | Student JWT |
| GET | `/api/auth/me` | Yes | — | Current principal |

## Quizzes (teacher)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/quizzes` | List owned quizzes |
| POST | `/api/quizzes` | Create quiz + questions |
| GET | `/api/quizzes/{id}` | Get quiz |
| PUT | `/api/quizzes/{id}` | Replace quiz |
| DELETE | `/api/quizzes/{id}` | Delete (also removes linked assignments) |
| GET | `/api/quizzes/{id}/export` | Export JSON |
| POST | `/api/quizzes/import` | Import JSON body (`QuizImport`) |
| GET | `/api/quizzes/topics` | The teacher's topics, as a list of names (suggestions for the question editor) |

Every question carries `topics`: a list of topic names (optional on input, default `[]`). It is accepted on create (`POST /api/quizzes`), update (`PUT /api/quizzes/{id}`) and import (`POST /api/quizzes/import`), and returned by get and export. Names are trimmed with internal spaces collapsed, and names differing only in case are one topic; at most 10 topics per question, each at most 80 characters. A topic new to the teacher is added to their topics; an existing one keeps the teacher's first spelling.

## Classes (teacher)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/classes` | List / create |
| GET/PUT/DELETE | `/api/classes/{id}` | Read / update / delete. PUT body: any of `name`, `require_password`, `mastery_threshold` (at least one) |
| GET/POST | `/api/classes/{id}/students` | List / add |
| PUT/DELETE | `/api/classes/{id}/students/{sid}` | Update / remove |
| POST | `/api/classes/{id}/students/import` | CSV multipart `file` |
| GET | `/api/classes/{id}/mastery` | Mastery report (JSON, below) |
| GET | `/api/classes/{id}/mastery/export` | Mastery report as CSV download (`mastery-class-{id}.csv`) |

`mastery_threshold` is the percent accuracy at which a topic counts as mastered: a whole number from 1 to 100 (default 80). It must be a JSON integer; `"80"` or `true` is refused with 422.

### Mastery report

`GET /api/classes/{id}/mastery` returns each current student's accuracy on each topic, from their answers in homework attempts and classroom live games:

```json
{
  "class_id": 1,
  "class_name": "Period 1",
  "mastery_threshold": 80,
  "window": 10,
  "min_answers": 3,
  "topics": ["Decimals", "Fractions"],
  "rows": [
    {
      "student_id": 7,
      "display_name": "Ada",
      "student_code": "ADA01",
      "cells": [
        { "topic": "Decimals", "answer_count": 2, "accuracy": null, "mastered": false },
        { "topic": "Fractions", "answer_count": 5, "accuracy": 80.0, "mastered": true }
      ]
    }
  ],
  "answers_without_topics": 3
}
```

Accuracy is over the student's most recent `window` answers on the topic, rounded to one decimal. With fewer than `min_answers` answers, `accuracy` is `null` ("not enough answers"). `answers_without_topics` counts answers on questions that had no topics; they are not in the table.

The CSV export has columns `student_code`, `display_name`, then one per topic; a cell is the accuracy (`80%`), marked `80% mastered` when mastered, or `not enough answers`.

## Assignments

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/assignments` | Teacher | List |
| POST | `/api/assignments` | Teacher | Create (`class_id`, `quiz_id`, `title?`, `due_at?`, `max_attempts?`, `score_policy?`) |
| PATCH | `/api/assignments/{id}` | Teacher | Update title/due/attempts/policy |
| POST | `/api/assignments/{id}/close` | Teacher | Close |
| POST | `/api/assignments/{id}/reopen` | Teacher | Reopen |
| DELETE | `/api/assignments/{id}` | Teacher | Delete |
| GET | `/api/assignments/{id}` | Teacher | Detail |
| GET | `/api/assignments/{id}/results` | Teacher | Per-student scores |
| GET | `/api/assignments/{id}/live` | Teacher or enrolled student | Active PIN if any |
| GET | `/api/assignments/mine` | Student | List + play stats |
| GET | `/api/assignments/mine/scores` | Student | Past game rows |

## Gradebook

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/gradebook/{class_id}` | Teacher | Matrix of scores |
| GET | `/api/gradebook/{class_id}/export` | Teacher | CSV download |

In both CSV exports (gradebook and mastery report), a text cell starting with `=`, `+`, `-` or `@` is prefixed with a single quote so spreadsheets keep it as text.

## Games (REST)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/games/info` | No | Public join hints |
| GET | `/api/games/pin/{pin}` | No | Peek lobby (`requires_student_code`, etc.) |
| GET | `/api/games/history` | Teacher | History list |
| GET/DELETE | `/api/games/history/{id}` | Teacher | Detail / delete |

## AI (teacher, optional)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ai/presets` | Google AI Studio models + lesson file limits |
| POST | `/api/ai/generate-quiz` | JSON: `model`, `api_key`, topic / `source_material`, optional `attachment` {`name`, `mime_type`, base64 `data`} (PDF or PNG/JPEG/WebP, max 10 MB, sent to Gemini as-is) |

API keys are **not** stored server-side. See [AI.md](AI.md).

---

## Socket.IO

Path: `/socket.io`  
Client: `socket.io-client` (same origin in production).

### Client → server

| Event | Payload (main fields) | Notes |
|-------|----------------------|-------|
| `create_game` | `{ token, quiz_id? }` or `{ token, assignment_id }` | Teacher JWT required |
| `join_game` | `{ pin, nickname? }` or `{ pin, student_code }` | Code required for assignment games |
| `leave_game` | `{ pin? }` | |
| `start_question` | `{ pin }` | Host only |
| `submit_answer` | `{ pin, option_index, elapsed_ms }` | During question |
| `next_question` / host controls | `{ pin }` | As implemented in host UI |
| `end_game` | `{ pin }` | Host |

Exact host control events: see `frontend/src/pages/HostGame.tsx` and `backend/app/socket_handlers.py`.

### Server → client

| Event | Purpose |
|-------|---------|
| `game_created` | PIN, QR, lobby |
| `lobby_update` | Players / status |
| `joined` / `player_joined` | Join ack |
| `question` | Prompt + options (no correct indices) |
| `question_ended` | Reveal + points |
| `leaderboard` | Rankings |
| `game_ended` | Final podium / persist |
| `error` | `{ message }` |

---

## Quiz JSON (import/export)

See [samples/README.md](../samples/README.md).
