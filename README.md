# Portfolio backend

A small FastAPI service, deployed on Vercel, that lets the portfolio site's `/admin` (the
[MajiDev](https://github.com/Majid-Ali-Watto/MajiDev) repository) publish to your GitHub profile:

- **Profile README**: commits `README.md` to your `<username>/<username>` repository (skipped when nothing changed)
- **Profile details**: name, bio, company, location, website, and "available for hire"
- **Daily refresh**: keeps the experience figures (e.g. "3Y 11M") in the published README, and a bio written with
  `Y-M-D`, current, computed exactly like the site does

`/admin → GitHub` builds the README and the profile details from your saved content and posts them to
`POST /github/publish`. The service accepts the request only from your admin account (it verifies the Firebase
sign-in token) and holds the GitHub token, so the token never reaches the browser or Firestore.

## 1. Create a GitHub token

GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token:

- **Repository access**: Only select repositories → your profile repository (`Majid-Ali-Watto/Majid-Ali-Watto`)
- **Repository permissions** → Contents: **Read and write** (for the README)
- **Account permissions** → Profile: **Read and write** (for the profile details)

If GitHub refuses a fine-grained token, a classic token with the `public_repo` and `user` scopes works too.

## 2. Deploy on Vercel

1. Vercel → **Add New → Project** → import this repository. Vercel detects FastAPI and loads `app` from `app.py`
   (which re-exports it from the `backend` package; see CLAUDE.md for the code layout).
2. Leave **Root Directory** as the repository root.
3. Add these **Environment Variables**, then deploy (redeploy after changing any of them):

   | Name | Value |
   |---|---|
   | `GITHUB_TOKEN` | the token from step 1 |
   | `FIREBASE_PROJECT_ID` | `portfolio-help-desk` (`VITE_APP_PROJECT_ID` in the site's `.env`) |
   | `ADMIN_UID` | your admin user's UID, the same one as in `firestore.rules` |
   | `ALLOWED_ORIGINS` | `https://majidev.netlify.app,http://localhost:5173` (where `/admin` runs, comma separated) |
   | `CRON_SECRET` | any long random string, e.g. from `openssl rand -hex 32`; Vercel sends it with the daily refresh |

4. Open `https://<your-project>.vercel.app/health`; it should answer `{"ok": true}`.

## 3. Point the site at it

Set `VITE_API_URL=https://<your-project>.vercel.app` in the site's `.env` (local) and in Netlify → Site configuration →
Environment variables, then redeploy the site. `/admin → GitHub` then shows a **Publish to GitHub** button.

## How the daily refresh works

`vercel.json` schedules `GET /github/refresh` once a day (03:17 UTC; on the Hobby plan Vercel may run it any time in
that hour). The README that `/admin` publishes wraps every experience figure in an invisible marker holding the job
dates it came from, e.g. `<!--experience:2025-09-15~Present,...-->**3Y 11M**<!--/experience-->`, plus a hidden copy
of a bio that uses `Y-M-D`. The refresh recomputes those figures for today (`backend/services/experience.py`, a port of the site's
`src/utils/getExpYears.js`) and commits only when one changed, so it never publishes unpublished edits from `/admin`.
To run it by hand: `curl -H "Authorization: Bearer $CRON_SECRET" https://<your-project>.vercel.app/github/refresh`.

## Keep in step with the site

The site and this service live in separate repositories but share three contracts. Change both sides together:

| Here | In the site repository |
|---|---|
| `PublishRequest` in `backend/models/github.py` (`readme`, `profile` fields and limits) | `src/admin/GitHubPublish.jsx` and `buildProfile` in `src/admin/githubReadme.js` |
| Marker formats in `backend/services/experience.py` (`experience`, `duration`, `github-bio`) | `src/admin/githubReadme.js` |
| `span` / `duration` / `total` in `backend/services/experience.py` | `src/utils/getExpYears.js` |

## Develop and test

With [uv](https://docs.astral.sh/uv/):

```bash
uv run pytest                       # tests mock GitHub and the token check; no secrets needed
uv run uvicorn app:app --reload     # http://localhost:8000, reads the variables above from the environment
```

Or with pip: `python -m venv .venv && . .venv/bin/activate && pip install fastapi httpx google-auth requests pytest uvicorn`.
