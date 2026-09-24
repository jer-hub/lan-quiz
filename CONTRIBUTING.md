# Contributing

Thanks for helping improve LanQuiz.

## How to contribute

1. Fork the repository (or create a branch if you have write access).
2. Use a feature branch: `git checkout -b feature/short-name`.
3. Follow [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) for local or Docker setup.
4. Keep changes focused — prefer small PRs (one feature or fix).
5. Update docs when behavior or env vars change.
6. Open a pull request with a short summary and test notes.

## Code style

- **Python:** match existing FastAPI / SQLAlchemy patterns; no unnecessary comments.
- **TypeScript/React:** functional components; reuse `api.ts` and `shared.ts` types.
- Avoid drive-by refactors unrelated to the PR.

## Testing checklist

Before opening a PR, verify what you touched:

- [ ] `docker compose up --build` (or local backend + `npm run dev`) starts cleanly
- [ ] `/api/health` returns OK
- [ ] Teacher register/login works
- [ ] If gameplay changed: create game → join → answer → end
- [ ] If assignments changed: host assignment game with student code
- [ ] If AI changed: presets + generate (with your own key) or extract-text only

## Commit messages

Prefer short, imperative subjects:

- `Add assignment reopen endpoint`
- `Fix Socket.IO CORS wildcard for LAN clients`
- `Document student assignment join flow`

## Scope we welcome

- Bug fixes, docs, accessibility, classroom UX, tests
- Self-paced assignment mode (planned product gap)
- Translations / i18n

## Out of scope for drive-by PRs

- Bundling Cursor skill packs under `.cursor/` (ignored; not part of the app)
- Committing `.env` or real JWT secrets / API keys
