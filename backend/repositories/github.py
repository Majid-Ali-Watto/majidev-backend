"""Data access for GitHub: raw REST calls for the token's own account, with no publishing rules of their own."""

import base64

import httpx

from backend.core.errors import UpstreamError
from backend.models.github import ReadmeFile

API = "https://api.github.com"


def _message(response: httpx.Response) -> str:
    """GitHub's error message: the JSON `message` when there is one (an outage page may be HTML or empty)."""
    try:
        body = response.json()
    except ValueError:
        return response.text[:200] or response.reason_phrase
    return body.get("message", response.text) if isinstance(body, dict) else response.text[:200]


class GitHubRepository:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _call(self, method: str, path: str, *, allow_404: bool = False, **kwargs) -> dict | None:
        """GitHub's JSON answer; None for a 404 when `allow_404`. Every other failure is an UpstreamError with GitHub's message."""
        try:
            response = await self.client.request(method, path, **kwargs)
        except httpx.HTTPError as err:
            raise UpstreamError(f"Could not reach GitHub: {err}") from err
        if allow_404 and response.status_code == 404:
            return None
        if response.is_error:
            raise UpstreamError(f"GitHub refused {method} {path}: {response.status_code} {_message(response)}")
        try:
            return response.json()
        except ValueError as err:
            raise UpstreamError(f"GitHub sent an unreadable answer to {method} {path}") from err

    async def user(self) -> dict:
        """The token's account (`login`, `bio`, `html_url`, ...)."""
        return await self._call("GET", "/user")

    async def update_user(self, fields: dict) -> dict:
        return await self._call("PATCH", "/user", json=fields)

    async def readme(self, repo: str) -> ReadmeFile | None:
        """README.md of `repo` ("owner/name"), or None if there is none."""
        found = await self._call("GET", f"/repos/{repo}/contents/README.md", allow_404=True)
        if found is None:
            return None
        return ReadmeFile(text=base64.b64decode(found["content"]).decode(), sha=found["sha"], url=found["html_url"])

    async def put_readme(self, repo: str, markdown: str, message: str, sha: str | None) -> dict | None:
        """Commits README.md (`sha` = the file it replaces, None to create it). None when GitHub answers 404."""
        body = {"message": message, "content": base64.b64encode(markdown.encode()).decode()}
        if sha:
            body["sha"] = sha
        return await self._call("PUT", f"/repos/{repo}/contents/README.md", allow_404=True, json=body)
