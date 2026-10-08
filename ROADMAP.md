# LanQuiz Roadmap — v1.1 to v1.4

> Generated 2026-10-08. Source: codebase review of `backend/app/*`, `frontend/src/*`, `docker-compose.yml`, `docs/*`.
> Constraint: single Docker image, LAN-first, SQLite stays.

## Milestones

- [ ] **v1.1-stable (Phase 0+1)** — Issues #1-6 — Don't lose games
- [ ] **v1.2-gameplay (Phase 2)** — Issues #7-10 — Fairness + new modes
- [ ] **v1.3-insight (Phase 3)** — Issues #11-13 — Teacher insight
- [ ] **v1.4-lan (Phase 4)** — Issues #14-15 — Offline + QR polish

Order: `1,2,3` parallel -> `4` -> `5` -> `6` -> `7` -> `8` -> `9+10` parallel -> `11-15` any order.

---

## Phase 0 — Hardening (blocks all)

### #1 [P0] Fail-fast on default JWT_SECRET + localhost HOST_IP `area: config`
- [ ] `backend/app/config.py:23` — `model_validator`: abort if `jwt_secret` still default in prod
- [ ] `backend/app/main.py:31-41` — warn if `host_ip in [localhost,127.0.0.1]`
- [ ] `docker-compose.yml:15`, `.env.example:13` — update comments
- [ ] `SECURITY.md` — trusted-LAN note
- Accept: bad secret exits non-zero; localhost warns.

### #2 [P0] Alembic baseline, fix FKs/cascades `area: db`
- [ ] Add `alembic.ini` + `backend/migrations/` baseline `0001` from `backend/app/models.py`
- [ ] Remove `try/except ALTER` in `backend/app/database.py`
- [ ] `GameHistory.quiz_id/teacher_id/class_id` -> FK `SET NULL`; `Assignment.results` cascade delete-orphan
- [ ] `Dockerfile` runs `alembic upgrade head` before uvicorn
- Accept: fresh + v1.0 DB both boot.

### #3 [P0] Smoke tests + CI `area: tests`
- [ ] `test_scoring.py` — `calculate_score` bounds `[BASE//2,BASE]`, wrong=0
- [ ] `test_schemas.py` — rejects 1/7 options, bad `correct_indices`, `time_limit` 5-120
- [ ] `test_quiz_routes.py` — `POST /import` not shadowed by `GET /{quiz_id}`
- [ ] `test_lobby.py` — 100-cap, nickname dedup, single-session code
- [ ] `test_gradebook.py` — `best` vs `latest`
- [ ] `.github/workflows/ci.yml` — add pytest + build
- Accept: CI green.

## Phase 1 — Don't lose games

### #4 [P1] Persist GameSession `depends: #2`
- [ ] `models.py` — new `ActiveGame{pin PK, payload_json}`
- [ ] `game_manager.py` — `save_snapshot()` on create/join/start/next; `load_snapshots()` in `lifespan()`
- [ ] `socket_handlers.py` — hook save; delete on `game_ended`
- [ ] `HostGame.tsx` — "Restored session" state
- Accept: `docker restart` keeps PIN + roster.

### #5 [P1] Auto-rejoin on reconnect
- [ ] `hooks/useSocket.ts` — persist `{pin,sid,nickname,student_code}` to `sessionStorage`
- [ ] `PlayPage.tsx` — re-emit `join_game{rejoin_sid}` on reconnect + "Reconnecting..." banner
- [ ] `game_manager.py:join_game` — reclaim slot <60s, keep score
- Accept: refresh keeps score, no ghost.

### #6 [P1] Rate-limit + nickname filter
- [ ] Add `slowapi`; limit `auth/*` 10/min, `join_game` 20/min
- [ ] `game_manager.py` — blocklist, `error{message}`
- [ ] `PlayPage.tsx` — error toast
- Accept: flood -> 429.

## Phase 2 — Gameplay

### #7 Per-player shuffle
- [ ] Extract `_shuffle_options` from `routers/ai.py` -> `utils/shuffle.py`
- [ ] `GameSession.option_map[sid]`; per-sid `question_started`; translate in `submit_answer`
- Accept: different order, correct scoring.

### #8 New question kinds `depends: #2`
- [ ] `Question{kind, answer_text}` + Alembic `0002`; `schemas.py` validators
- [ ] `routers/quizzes.py` import compat (`kind=mc` default); update `samples/`
- [ ] `shared.ts:QuestionKind`; `QuizEditor.tsx` kind editor; `PlayPage.tsx` + `HostGame.tsx` render
- [ ] `calculate_score` short-answer normalize
- Accept: mc/tf/ordering/short all play; old JSON loads.

### #9 Team mode
- [ ] `Player.team`; `create_game{team_mode,teams}`; lobby/leaderboard/end by team
- [ ] `HostGame.tsx` team lobby + `Podium.tsx`; `PlayPage.tsx` picker
- Accept: 6 teams correct winner.

### #10 Self-paced homework (largest)
- [ ] `Attempt{assignment_id,student_id,score,answers_json}` + schemas
- [ ] `routers/assignments.py` — `POST /{id}/attempts`, `POST /attempts/{id}/submit`, include in `_pick_score/_build_gradebook`
- [ ] `api.ts:createAttempt/submitAttempt`; new `AttemptPage.tsx`; `StudentDashboard.tsx` + `AssignmentsPage.tsx:458` badges
- Accept: solo attempt without host; gradebook unified.

## Phase 3 — Insight

### #11 Item analysis
- [ ] `routers/games.py:GET /history/{id}/analysis` from `results_json`
- [ ] `assignments.py:GET /{id}/results` aggregate; `api.ts`, `shared.ts:QuestionAnalysis`
- [ ] `HistoryPage.tsx` + `ClassDetailPage.tsx` % correct + histogram + CSV column
- Accept: "Q3 22% correct" visible.

### #12 Uploads dir `depends: #2`
- [ ] `main.py` mount `/uploads` from `DATA_DIR/uploads`
- [ ] `routers/quizzes.py:POST /upload-image` (Pillow verify, 2MB, uuid)
- [ ] `QuizEditor.tsx` picker -> url; `Play/Game.tsx` render `url|data:`
- Accept: 10-image quiz <100KB JSON.

### #13 Roster + vi/en
- [ ] `routers/classes.py:import_roster` -> `{added, skipped:[{row,reason}]}` + `utf-8-sig`
- [ ] `ClassDetailPage.tsx` template + error table; `ClassesPage.tsx` onboarding
- [ ] `i18n.ts` vi/en + `App.tsx` toggle, `Home/Play/StudentDashboard` first
- Accept: row 14 error precise; toggle persists.

## Phase 4 — LAN polish

### #14 PWA + offline play
- [ ] `vite-plugin-pwa` in `vite.config.ts`; manifest, `sw.js`
- [ ] `index.html` meta/icons; `PlayPage.tsx` offline banner; `useSocket.ts` backoff
- Accept: Lighthouse PWA pass; offline join form renders.

### #15 HOST_IP + QR polish `pairs: #1`
- [ ] `/api/health` -> `{public_base_url, host_ip_is_loopback}`; `utils/qr.py` uses base_url
- [ ] `HostGame.tsx` large QR + copy + `n/100` + localhost warning; `HomePage.tsx` host/join cards
- [ ] `docs/CLASSROOM.md` LAN checklist
- Accept: QR -> `/play?pin=XXXX`; wrong IP warns.

---

## Board suggestion

Now: #1-6 | Next: #7-10 | Later: #11-15
