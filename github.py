"""The GitHub calls the API makes, authenticated with the server's GITHUB_TOKEN."""

import base64
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException

from auth import setting

API = "https://api.github.com"
COMMIT_MESSAGE = "Update profile README from the portfolio admin"
REFRESH_MESSAGE = "Refresh experience durations"


class GitHub:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def _call(self, method: str, path: str, *, allow_404: bool = False, **kwargs) -> dict | None:
        try:
            response = await self.client.request(method, path, **kwargs)
        except httpx.HTTPError as err:
            raise HTTPException(502, f"Could not reach GitHub: {err}") from err
        if allow_404 and response.status_code == 404:
            return None
        if response.is_error:
            message = response.json().get("message", response.text) if response.content else response.reason_phrase
            raise HTTPException(502, f"GitHub refused {method} {path}: {response.status_code} {message}")
        return response.json()

    async def login(self) -> str:
        return (await self._call("GET", "/user"))["login"]

    async def readme(self) -> tuple[str, dict | None]:
        """The profile repository (<login>/<login>) and its current README (with decoded `text`), or None."""
        login = await self.login()
        repo = f"{login}/{login}"
        current = await self._call("GET", f"/repos/{repo}/contents/README.md", allow_404=True)
        if current:
            current["text"] = base64.b64decode(current["content"]).decode()
        return repo, current

    async def update_readme(self, markdown: str, message: str = COMMIT_MESSAGE) -> dict:
        """Commits README.md to the profile repository (<login>/<login>), unless it already has this content."""
        repo, current = await self.readme()
        if current and current["text"] == markdown:
            return {"status": "unchanged", "url": current["html_url"]}

        body = {"message": message, "content": base64.b64encode(markdown.encode()).decode()}
        if current:
            body["sha"] = current["sha"]
        result = await self._call("PUT", f"/repos/{repo}/contents/README.md", allow_404=True, json=body)
        if result is None:
            raise HTTPException(502, f"Repository {repo} not found; create it on GitHub to get a profile README")
        return {"status": "updated", "url": result["content"]["html_url"], "commit": result["commit"]["html_url"]}

    async def bio(self) -> str:
        return (await self._call("GET", "/user")).get("bio") or ""

    async def update_profile(self, fields: dict) -> dict:
        user = await self._call("PATCH", "/user", json=fields)
        return {"status": "updated", "url": user["html_url"]}


async def github_client() -> AsyncIterator[GitHub]:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {setting('GITHUB_TOKEN')}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    async with httpx.AsyncClient(base_url=API, headers=headers, timeout=20) as client:
        yield GitHub(client)
