"""Wires repositories and services into routes. Tests override `github_repository` instead of hitting the network."""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
from fastapi import Depends

from backend.core.config import setting
from backend.repositories.github import API, GitHubRepository
from backend.services.github import GitHubProfileService


async def github_repository() -> AsyncIterator[GitHubRepository]:
    """GitHub, authenticated with the server's GITHUB_TOKEN; one HTTP client per request."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {setting('GITHUB_TOKEN')}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(base_url=API, headers=headers, timeout=20) as client:
        yield GitHubRepository(client)


def github_profile_service(github: Annotated[GitHubRepository, Depends(github_repository)]) -> GitHubProfileService:
    return GitHubProfileService(github)
