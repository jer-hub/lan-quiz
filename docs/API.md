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
| POST | `/api/auth/register` | No | `{ username, password }` | Create teacher |
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

## Classes (teacher)

| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/classes` | List / create |
| GET/PUT/DELETE | `/api/classes/{id}` | Read / rename / delete |
| GET/POST | `/api/classes/{id}/students` | List / add |
| PUT/DELETE | `/api/classes/{id}/students/{sid}` | Update / remove |
| POST | `/api/classes/{id}/students/import` | CSV multipart `file` |

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
| GET | `/api/ai/presets` | Providers/models + extract limits |
| POST | `/api/ai/extract-text` | Multipart `file` → text (PDF/DOCX/TXT/MD, max 5 MB) |
| POST | `/api/ai/generate-quiz` | JSON: provider, model, `api_key`, topic / `source_material`, … |

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
