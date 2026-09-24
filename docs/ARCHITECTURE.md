# Architecture

## Overview

```text
┌─────────────┐     HTTP / Socket.IO      ┌──────────────────────────┐
│  Browsers   │ ◄────────────────────────► │  Docker: lanquiz         │
│ teacher /   │     same LAN               │  FastAPI + python-socketio│
│ student /   │                            │  SQLite (./data)          │
│ guest play  │                            │  Static React SPA         │
└─────────────┘                            └──────────────────────────┘
         │                                              │
         │  optional (AI generate only)                 │
         └──────────────► Groq / OpenAI / … ◄───────────┘
```

- **One container** serves API, WebSocket, and built frontend.
- **Live game state** is in-memory (`GameManager`); finished games persist to SQLite.
- **JWT** auth for teachers and rostered students. Guests play without tokens on casual games.

## Components

| Piece | Location | Role |
|-------|----------|------|
| FastAPI app | `backend/app/main.py` | REST routes, SPA fallback, lifespan DB init |
| Socket.IO | `backend/app/socket_handlers.py` | Lobby, questions, answers, reveal, end |
| Game engine | `backend/app/game_manager.py` | PINs, sessions, scoring, leaderboards |
| ORM | `backend/app/models.py` | Users, quizzes, classes, students, assignments, history |
| Auth | `backend/app/auth.py` | bcrypt passwords, JWT create/verify |
| AI proxy | `backend/app/routers/ai.py` | Teacher-only; browser API key → provider |
| Text extract | `backend/app/text_extract.py` | PDF/DOCX/TXT/MD → text (no persistence) |
| Frontend | `frontend/src/` | React Router SPA |

## Data model (simplified)

```text
User (teacher)
  ├── Quiz ── Question[]
  └── ClassRoom
        ├── Student[]
        └── Assignment ──► Quiz
              └── GameHistory[] ── GameResult[] (optional student_id)
```

SQLite file: `DATA_DIR/lanquiz.db` (default volume `./data`).

Startup runs `create_all` plus lightweight `ALTER TABLE` patches for new columns (e.g. `max_attempts`, `score_policy`).

## Live game flow

```text
Teacher create_game (quiz_id | assignment_id)
        │
        ▼
   Lobby (PIN / QR)
        │
 Students join_game (nickname | student_code)
        │
 Teacher start_question → question → answers → reveal → …
        │
   game_ended → persist GameHistory (+ GameResult rows)
```

Assignment games set `requires_student_code` and validate the code against the class roster. Max attempts and due dates are enforced at host/join.

## Frontend routes (selected)

| Path | Who |
|------|-----|
| `/` | Home |
| `/play` | Join live game |
| `/teacher/login`, `/teacher/register` | Teacher auth |
| `/teacher/*` | Quizzes, classes, assignments, history |
| `/student/login`, `/student` | Student portal |
| `/host/game/:quizId`, `/host/game/assignment/:id` | Host UI |

## Offline / LAN

- Live play needs only LAN connectivity between devices and the host.
- Internet is required only for: Docker image pull (first build), and optional AI generation.
