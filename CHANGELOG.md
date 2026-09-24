# Changelog

All notable changes to LanQuiz are documented here.

## [1.0.0] — 2026-09-24

### Added

- Live Kahoot-style games (PIN/QR, timed scoring, leaderboard, podium)
- Teacher JWT auth, quiz CRUD, JSON import/export
- Classes, roster, CSV import, join codes
- Assignments with due dates, close/reopen, max attempts, best/latest score policy
- Assignment results, live PIN surface, student dashboard completion stats
- Gradebook + CSV export
- Optional AI quiz generator (Groq defaults) with LAN-side PDF/DOCX/TXT/MD extract
- Docker Compose single-container deploy
- Documentation under `docs/`

### Notes

- Assignments are **live-hosted** only (no self-paced student start yet)
- AI keys stay in the browser; never stored in SQLite
