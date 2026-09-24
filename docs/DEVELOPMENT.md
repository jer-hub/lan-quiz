# Development

## Prerequisites

- Python 3.12+
- Node.js 22+ (or compatible LTS)
- Docker (recommended for full stack parity)

## Environment

Copy `.env.example` → `.env` at the repo root.

| Variable | Default | Meaning |
|----------|---------|---------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | HTTP port |
| `HOST_IP` | `localhost` | Host used in QR / join URLs |
| `DATA_DIR` | `/app/data` (Docker) | SQLite directory |
| `LOG_LEVEL` | `INFO` | Logging |
| `SCORE_BASE` | `1000` | Max points per correct answer |
| `JWT_SECRET` | dev placeholder | **Change for real use** |
| `JWT_EXPIRE_HOURS` | `72` | Token lifetime |

## Docker (recommended)

```bash
cp .env.example .env
# set HOST_IP and JWT_SECRET
docker compose up --build
```

- App: http://localhost:8000  
- Data volume: `./data`  
- Rebuild after backend/frontend changes: `docker compose up --build`

Healthcheck hits `/api/health`.

## Local backend

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt

# Windows PowerShell examples:
$env:DATA_DIR = "..\data"
$env:HOST_IP = "localhost"
$env:JWT_SECRET = "dev-secret"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Static SPA is only present in the Docker image (`./static`). Locally, run the Vite dev server for the UI.

## Local frontend

```bash
cd frontend
npm install
npm run dev
```

Vite proxies `/api` and `/socket.io` to `http://127.0.0.1:8000` (see `vite.config.ts`).

Production build:

```bash
cd frontend
npm run build
```

## Database

- File: `{DATA_DIR}/lanquiz.db`
- Tables created on startup; additive SQLite column patches applied for newer fields
- Reset: stop the app, delete `./data/lanquiz.db*`, start again

## Sample data

Import via UI or:

```bash
curl -X POST http://127.0.0.1:8000/api/quizzes/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary @samples/sample-quiz.json
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Other devices can’t connect | Set `HOST_IP` to LAN IP; allow TCP **8000** on the host firewall |
| Host create game stuck / WS 403 | Socket.IO CORS must be `"*"` string (already configured); rebuild image |
| 401 on teacher routes | Register/login; check `JWT_SECRET` didn’t change mid-session |
| Class game rejects nickname | Use **student code** from roster |
| Duplicate student code login | Pass class **join code** |
| AI rate limit | Wait / change model / new key; see [AI.md](AI.md) |
| Empty quizzes after upgrade | Delete DB if schema from a very old build conflicts |

## CI

GitHub Actions (`.github/workflows/ci.yml`) builds the frontend and installs Python deps to catch basic breakages. Docker image build is optional in CI to save minutes.
