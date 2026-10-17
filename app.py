"""Portfolio backend, deployed on Vercel: publishes the site's content to the owner's GitHub profile.

/admin builds the README and profile details from the saved content and posts them here; this service holds the
GitHub token, so it never reaches the browser.
"""

import os
import secrets
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auth import require_admin, setting
from experience import bio_from_readme, refresh_readme
from github import REFRESH_MESSAGE, GitHub, github_client

app = FastAPI(title="Majidev backend", docs_url=None, redoc_url=None, openapi_url=None)

# The admin page's origins, e.g. "https://majidev.netlify.app,http://localhost:5173"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",") if origin.strip()],
    allow_methods=["POST"],
    allow_headers=["Authorization", "Content-Type"],
)


BIO_LIMIT = 160  # GitHub's limit


class Profile(BaseModel):
    """GitHub profile details; fields left out are not changed."""

    name: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=BIO_LIMIT)
    company: str | None = Field(None, max_length=255)
    location: str | None = Field(None, max_length=255)
    blog: str | None = Field(None, max_length=255)
    hireable: bool | None = None


class PublishRequest(BaseModel):
    readme: str | None = Field(None, max_length=200_000)
    profile: Profile | None = None


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/github/publish", dependencies=[Depends(require_admin)])
async def publish(body: PublishRequest, github: Annotated[GitHub, Depends(github_client)]) -> dict:
    """Publishes whichever of `readme` and `profile` the request includes."""
    result = {}
    if body.readme is not None:
        result["readme"] = await github.update_readme(body.readme)
    if body.profile is not None:
        result["profile"] = await github.update_profile(body.profile.model_dump(exclude_none=True))
    return result


def require_cron(authorization: str | None = Header(default=None)) -> None:
    """Vercel Cron sends "Authorization: Bearer <CRON_SECRET>" (vercel.json schedules the call)."""
    if not secrets.compare_digest(authorization or "", f"Bearer {setting('CRON_SECRET')}"):
        raise HTTPException(401, "Not the scheduled job")


@app.get("/github/refresh", dependencies=[Depends(require_cron)])
async def refresh(github: Annotated[GitHub, Depends(github_client)]) -> dict:
    """Daily: recomputes the experience durations in the published README and bio (see experience.py)."""
    today = date.today()
    _, current = await github.readme()
    if not current:
        return {"readme": {"status": "missing"}}
    markdown = refresh_readme(current["text"], today)
    result = {"readme": await github.update_readme(markdown, REFRESH_MESSAGE)}

    bio = bio_from_readme(markdown, today)
    if bio is not None and len(bio) <= BIO_LIMIT:
        result["profile"] = await github.update_profile({"bio": bio}) if bio != await github.bio() else {"status": "unchanged"}
    return result
