"""Request and response bodies of the /github routes, and the README file the repository returns.

`Profile` and `PublishRequest` are a contract with the site (src/admin/GitHubPublish.jsx, buildProfile in
src/admin/githubReadme.js): change both repositories together.
"""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

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


class Change(BaseModel):
    """What happened to one target (the README or the profile); `url` points at it on GitHub."""

    status: Literal["updated", "unchanged", "missing"]
    url: str | None = None
    commit: str | None = None


class GitHubResult(BaseModel):
    """Only the targets the call touched are present."""

    readme: Change | None = None
    profile: Change | None = None


@dataclass(frozen=True)
class ReadmeFile:
    """README.md as stored in a repository."""

    text: str
    sha: str
    url: str
