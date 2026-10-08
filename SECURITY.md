# Security

## Secrets

| Secret | Where | Guidance |
|--------|--------|----------|
| `JWT_SECRET` | `.env` on the host | Change from the example before any shared/classroom deploy. App refuses to boot with the default unless `ALLOW_DEFAULT_SECRET=true` (local dev only) |
| Teacher/student passwords | SQLite (bcrypt) | Roster default password = username; teacher import: blank password defaults to username (min 6). First teacher self-registers, then bulk-imports via host dashboard |
| `HOST_IP` | `.env` / compose | Must be your LAN IP (e.g. `192.168.1.42`) for QR/join URLs. `localhost` triggers a startup warning and `GET /api/health → host_ip_is_loopback:true` |
| Teacher/student passwords | SQLite (bcrypt) | Default student password = student code — change for real classes |
| AI API keys | Browser `localStorage` only | Never commit keys; LanQuiz does not store them in the DB |

Never commit `.env`. Use `.env.example` as the template.

## Network model

LanQuiz is designed for a **trusted LAN** (classroom / party):

- CORS and Socket.IO allow broad origins for easy device join.
- Do not expose the port to the public internet without a reverse proxy, HTTPS, and a hardened auth setup.

## Reporting issues

If you find a security-sensitive bug (auth bypass, data leak across teachers/classes, etc.):

1. Prefer a private report to the maintainer if contact is listed on the GitHub repo.
2. Otherwise open a GitHub issue **without** publishing exploit details or sample credentials from a live school.

## Data

- Quiz and classroom data live in `./data/lanquiz.db` on the host.
- Treat that file as sensitive (student names, codes, scores).
- Uploaded AI lesson files are not persisted; extracted text is sent only to the configured AI provider during generate.
