# CLAUDE.md — Claude Code Instructions

## Project
FastAPI service deployed on Vercel (zero config: `app` in `app.py`, dependencies from `pyproject.toml`, Python ≥ 3.12).
It publishes the portfolio site's content to the owner's GitHub profile and keeps the experience figures there current.
The site is a separate repository, MajiDev (sibling folder `../MajiDev`); its `/admin` calls this service.

## Do Not Read
Never read, index, or suggest changes inside:
- `.venv/`
- `.vercel/`
- `__pycache__/`, `.pytest_cache/`

## Layout

| File | Purpose |
|---|---|
| `app.py` | FastAPI app, CORS, request models (`Profile`, `PublishRequest`) and routes |
| `auth.py` | `require_admin` (verifies the admin's Firebase ID token with `google-auth`) and `setting()` for required env vars |
| `github.py` | `GitHub` client (httpx) for README commits and profile updates; `github_client` dependency holds `GITHUB_TOKEN` |
| `experience.py` | Experience maths and the README markers the daily refresh recomputes |
| `vercel.json` | Vercel Cron: `GET /github/refresh` daily |
| `tests/` | pytest; GitHub is mocked with `httpx.MockTransport`, token verification with monkeypatch |

## Routes
- `GET /health`: liveness
- `POST /github/publish`: admin only (Firebase ID token, `sub` must be `ADMIN_UID`); commits the README to `<login>/<login>` (skipped when unchanged) and/or PATCHes `/user`
- `GET /github/refresh`: cron only (`Authorization: Bearer <CRON_SECRET>`); recomputes marked experience figures in the published README and the bio, committing only on change

## Environment
`GITHUB_TOKEN`, `FIREBASE_PROJECT_ID`, `ADMIN_UID`, `ALLOWED_ORIGINS` (comma separated), `CRON_SECRET`. Read them through
`auth.setting()` so a missing one is a clear 500, never a crash. Secrets live only in Vercel env vars, never in code or responses.

## Key Patterns
- Stateless: no database. `/admin` sends the finished README and profile fields; the refresh reads only the README on GitHub, so it never publishes edits the admin has not published
- GitHub failures surface as `HTTPException(502)` with GitHub's message (`GitHub._call`); keep that for new calls
- New GitHub calls go through `GitHub`, and tests override the `github_client` dependency rather than hitting the network

## Contracts with the site (change both repositories together)

| Here | In MajiDev |
|---|---|
| `PublishRequest` / `Profile` fields and limits in `app.py` | `src/admin/GitHubPublish.jsx`, `buildProfile` in `src/admin/githubReadme.js` |
| Marker formats in `experience.py` (`<!--experience:…-->`, `<!--duration:…-->`, `<!--github-bio:…-->`) | `src/admin/githubReadme.js` |
| `span` / `duration` / `total` in `experience.py` | `src/utils/getExpYears.js` (results must stay identical, including its edge cases) |

## Commands
```bash
uv run pytest                     # tests; no secrets or network needed
uv run uvicorn app:app --reload   # local server on :8000 (set the env vars above first)
```
