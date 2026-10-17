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

`app.py` only re-exports `app` for Vercel; the code is the `backend` package, layered so each layer only calls the one below:
routers → services → repositories, with models shared between them.

| Path | Purpose |
|---|---|
| `backend/main.py` | FastAPI app: CORS, the `AppError` handler, router registration |
| `backend/routers/` | HTTP layer: paths, access checks, request/response models; no business rules |
| `backend/services/` | Business rules (`github.py`: publish and the daily refresh; `experience.py`: experience maths and README markers) |
| `backend/repositories/` | Data access to outside systems (`github.py`: raw GitHub REST calls via httpx) |
| `backend/models/` | Pydantic request/response bodies and internal records |
| `backend/dependencies.py` | Builds repositories and services per request (`github_repository`, `github_profile_service`) |
| `backend/core/` | `config.setting()` for env vars, `security` (`require_admin`, `require_cron`), `errors` (`AppError`, `ConfigError`, `UpstreamError`) |
| `vercel.json` | Vercel Cron: `GET /github/refresh` daily |
| `tests/` | pytest; GitHub is mocked with `httpx.MockTransport`, token verification with monkeypatch |

A new feature adds a router (registered in `main.py`), a service for its rules, a repository per outside system, and its models.

## Routes
- `GET /health`: liveness
- `POST /github/publish`: admin only (Firebase ID token, `sub` must be `ADMIN_UID`); commits the README to `<login>/<login>` (skipped when unchanged) and/or PATCHes `/user`
- `GET /github/refresh`: cron only (`Authorization: Bearer <CRON_SECRET>`); recomputes marked experience figures in the published README and the bio, committing only on change

## Environment
`GITHUB_TOKEN`, `FIREBASE_PROJECT_ID`, `ADMIN_UID`, `ALLOWED_ORIGINS` (comma separated), `CRON_SECRET`. Read them through
`backend.core.config.setting()` so a missing one is a clear 500, never a crash. Secrets live only in Vercel env vars, never in code or responses.

## Key Patterns
- Stateless: no database. `/admin` sends the finished README and profile fields; the refresh reads only the README on GitHub, so it never publishes edits the admin has not published
- Services and repositories raise `AppError` subclasses, never `HTTPException`; `main.py` answers them as `{"detail": …}`. GitHub failures are `UpstreamError` (502) with GitHub's message (`GitHubRepository._call`); keep that for new calls
- New GitHub calls go through `GitHubRepository`, and tests override the `github_repository` dependency rather than hitting the network

## Contracts with the site (change both repositories together)

| Here | In MajiDev |
|---|---|
| `PublishRequest` / `Profile` fields and limits in `backend/models/github.py` | `src/admin/GitHubPublish.jsx`, `buildProfile` in `src/admin/githubReadme.js` |
| Marker formats in `backend/services/experience.py` (`<!--experience:…-->`, `<!--duration:…-->`, `<!--github-bio:…-->`) | `src/admin/githubReadme.js` |
| `span` / `duration` / `total` in `backend/services/experience.py` | `src/utils/getExpYears.js` (results must stay identical, including its edge cases) |

## Commands
```bash
uv run pytest                     # tests; no secrets or network needed
uv run uvicorn app:app --reload   # local server on :8000 (set the env vars above first)
```
