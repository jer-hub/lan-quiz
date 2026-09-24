# LanQuiz

**Self-hosted Kahoot-style multiplayer quizzes for your classroom LAN.**

Teachers manage quizzes, classes, and assignments. Students join with roster codes or live PINs. After Docker setup, **live games work fully offline** on your local network.

[Features](#features) · [Quick start](#quick-start) · [Docs](#documentation) · [Development](#development) · [License](#license)

---

## Features

| Area | What you get |
|------|----------------|
| **Live games** | PIN/QR lobby, timed questions, speed scoring, leaderboard, podium |
| **Teachers** | Register/login (JWT), own quizzes, import/export JSON |
| **Classes** | Rosters, join codes, CSV import, gradebook + CSV export |
| **Assignments** | Due dates, close/reopen, max attempts, best/latest score, live PIN, results |
| **Students** | Portal for assignments/scores; roster-gated join for class games |
| **Casual mode** | Host any quiz without an assignment (nickname join) |
| **AI (optional)** | Groq/OpenAI/OpenRouter quiz draft generator; LAN-side PDF/DOCX/TXT/MD extract |

Stack: **FastAPI + Socket.IO + SQLite** · **React + Vite + TypeScript + Tailwind** · **Docker**

---

## Quick start

### Requirements

- [Docker](https://docs.docker.com/get-docker/) + Docker Compose
- Devices on the **same Wi‑Fi/LAN** as the host PC

### 1. Find your LAN IP

Other phones/laptops need your computer’s Wi‑Fi address (not `localhost`).

- **Windows:** `ipconfig` → IPv4 under Wi‑Fi (e.g. `192.168.1.42`)
- **macOS / Linux:** `hostname -I` or `ip addr`

### 2. Configure and run

```bash
git clone https://github.com/YOUR_USER/lan-quiz.git
cd lan-quiz
cp .env.example .env
# Edit .env: set HOST_IP to your LAN IP, change JWT_SECRET
docker compose up --build
```

Open **http://localhost:8000** on the host, or **http://YOUR_LAN_IP:8000** on other devices.

### 3. First classroom session

1. **Teacher login** → register an account  
2. Create a quiz (or import [`samples/sample-quiz.json`](samples/sample-quiz.json))  
3. **Classes** → create a class (note the **join code**)  
4. Add students (`display_name` + `student_code`; default password = student code) or CSV import  
5. **Assignments** → assign quiz → optional due date / max attempts → **Host live game**  
6. Students open `/play` with PIN + **student code** (or use the live PIN on their dashboard)  
7. Review **Gradebook** or assignment **Results** (CSV export available)

**Casual party:** from a quiz, **Start game** without an assignment — guests join with PIN + nickname.

---

## How assignments work (students)

Assignments are **live class games**, not self-paced homework.

1. Teacher hosts the assignment → PIN appears  
2. Student joins `/play` with PIN + roster **student code**  
3. Student answers questions in real time  
4. Scores roll into the assignment / gradebook  

Students **cannot** start the quiz alone from the dashboard. Details: [docs/CLASSROOM.md](docs/CLASSROOM.md).

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/CLASSROOM.md](docs/CLASSROOM.md) | Teachers, students, assignments, gradebook |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design, data model, Socket.IO flow |
| [docs/API.md](docs/API.md) | REST + Socket.IO reference |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | Local dev, Docker, env vars, troubleshooting |
| [docs/AI.md](docs/AI.md) | Optional AI quiz generator + file extract |
| [samples/README.md](samples/README.md) | Sample quiz JSON format |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to contribute |
| [SECURITY.md](SECURITY.md) | Secrets, auth, reporting |

---

## Scoring

```text
points = round(BASE × (1 − (elapsed ÷ time_limit) ÷ 2))
```

Clamped to `[BASE/2, BASE]` (default BASE = 1000 → 500–1000). Wrong answers score **0**.

---

## Development

```bash
# Backend
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
set DATA_DIR=..\data
set HOST_IP=localhost
set JWT_SECRET=dev-secret
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (proxies API + Socket.IO → :8000)
cd frontend
npm install
npm run dev
```

Full guide: [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

---

## Project layout

```text
lan-quiz/
├── backend/app/          # FastAPI + Socket.IO + SQLite
├── frontend/src/         # React SPA
├── samples/              # Example quiz JSON
├── docs/                 # Extended documentation
├── data/                 # SQLite volume (gitignored *.db)
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## License

[MIT](LICENSE) — free for classrooms, parties, and LAN events.
