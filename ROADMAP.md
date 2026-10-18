# LanQuiz Roadmap

> Rewritten after a code audit. A box is checked only when the code path exists in the repo. Anything not verified stays open.
> Constraint: single Docker image, LAN-first, SQLite stays.

## Shipped (v1.0 – v1.4)

- [x] Fail-fast on default `JWT_SECRET` (`backend/app/config.py`, `ensure_secure`)
- [x] Localhost `HOST_IP` warning at startup (`backend/app/main.py`)
- [x] Alembic migrations `0001`–`0005` (`backend/migrations/versions/`)
- [x] Pytest suite and CI workflow (`backend/tests/`, `.github/workflows/ci.yml`)
- [x] Live game snapshots restored on restart (`backend/app/session_store.py`, `ActiveGame`)
- [x] Server-side reclaim of a disconnected player's slot within the grace period (`game_manager.join_game`)
- [x] Per-player option shuffle (`backend/app/utils/shuffle.py`)
- [x] Question kinds: multiple choice, true/false, ordering, short answer
- [x] Team mode (`team_mode`, `teams`, team scores)
- [x] Self-paced homework attempts (`Attempt`, `AttemptPage.tsx`)
- [x] Item analysis for past games (`backend/app/analysis.py`, `GET /api/games/history/{id}/analysis`)
- [x] Image uploads with Pillow verification (`POST /api/quizzes/upload-image`)
- [x] Roster CSV import with skipped-row report
- [x] Vietnamese / English UI toggle (`frontend/src/i18n.ts`)
- [x] PWA setup (`vite-plugin-pwa` in `frontend/vite.config.ts`)

## Not shipped from the old v1.1–v1.4 plan

- [ ] Rate limiting on auth and join endpoints. No limiter library or 429 path exists.
- [ ] Nickname blocklist.
- [ ] Client-side auto-rejoin with a "Reconnecting…" banner. Server reclaim exists; confirm the client re-emits `join_game` before checking this off.
- [ ] Offline join form and backoff in `useSocket.ts`. Confirm before checking off.

## v1.5 — Hardening follow-ups

Items from the security review (2026-10). Each needs a regression test.

- [ ] **Student join identity.** Add a per-class setting "require student password to join", off by default. Classroom joins check the password when the setting is on. (Review item 5)
- [ ] **Custom AI provider URL.** Require `https`. Block loopback, link-local and private addresses unless `ALLOW_PRIVATE_AI_PROVIDERS=true`, which local models such as Ollama need. Stop echoing provider error bodies beyond a short fixed message. (Review item 6)
- [ ] **Student passwords.** Enforce a minimum length of 6 on roster import, matching teacher import. When a password is omitted, generate a random initial password and return it once in the import response. Stop defaulting to the student code. (Review item 7)
- [ ] **Teacher registration.** Disable public self-registration once a teacher account exists. Enable it again only with `ALLOW_TEACHER_REGISTRATION=true`. (Review item 8)
- [ ] **Upload limits.** Enforce the 2 MB image limit while reading the body. Cap roster and teacher CSV import at a fixed row count. (Review low item 11)
- [ ] **Secure join codes.** Generate class join codes and PINs with `secrets`, not `random`. (Review low item 12)

## v1.6 — Teacher experience

- [ ] **Ordering reveal.** After an ordering question, show the canonical order numbered 1 to n, and highlight the student's submitted sequence separately. The current reveal marks every option green, which hides the sequence that scored.
- [ ] Rate limiting and nickname blocklist (carried over from above).
- [ ] Client-side auto-rejoin, if the audit shows it is missing.
- [ ] Gradebook: show live and homework attempts side by side per student.

## Board suggestion

Now: v1.5 hardening | Next: v1.6 teacher experience
