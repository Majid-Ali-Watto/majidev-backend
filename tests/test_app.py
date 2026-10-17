import base64
import json
import os

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ.update(
    FIREBASE_PROJECT_ID="demo-project",
    ADMIN_UID="admin-uid",
    GITHUB_TOKEN="test-token",
    ALLOWED_ORIGINS="https://site.example",
    CRON_SECRET="cron-secret",
)

import auth  # noqa: E402
from app import app  # noqa: E402
from github import API, GitHub, github_client  # noqa: E402

ADMIN_CLAIMS = {"iss": "https://securetoken.google.com/demo-project", "sub": "admin-uid"}
AUTH = {"Authorization": "Bearer signed-in"}


@pytest.fixture
def claims(monkeypatch):
    """Claims the (mocked) Firebase token verification returns; mutate to simulate other users."""
    current = dict(ADMIN_CLAIMS)

    def verify(token, request, audience, clock_skew_in_seconds):
        assert audience == "demo-project"
        if token != "signed-in":
            raise ValueError("bad token")
        return current

    monkeypatch.setattr(auth.id_token, "verify_firebase_token", verify)
    return current


class FakeGitHub:
    """Answers GitHub API calls from `routes` ({(method, path): (status, json)}) and records every request."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        self.calls.append((request.method, request.url.path, body))
        status, payload = self.routes.get((request.method, request.url.path), (404, {"message": "Not Found"}))
        return httpx.Response(status, json=payload)


@pytest.fixture
def github():
    fake = FakeGitHub({("GET", "/user"): (200, {"login": "octo"})})

    async def client():
        async with httpx.AsyncClient(base_url=API, transport=httpx.MockTransport(fake.handler)) as http:
            yield GitHub(http)

    app.dependency_overrides[github_client] = client
    yield fake
    app.dependency_overrides.clear()


client = TestClient(app)
README_PATH = "/repos/octo/octo/contents/README.md"


def encoded(text):
    return base64.b64encode(text.encode()).decode()


def test_health():
    assert client.get("/health").json() == {"ok": True}


@pytest.mark.parametrize(
    ("headers", "status"),
    [({}, 401), ({"Authorization": "Basic x"}, 401), ({"Authorization": "Bearer forged"}, 401)],
)
def test_rejects_missing_or_invalid_sign_in(claims, github, headers, status):
    assert client.post("/github/publish", json={"readme": "x"}, headers=headers).status_code == status
    assert github.calls == []


@pytest.mark.parametrize("change", [{"sub": "someone-else"}, {"iss": "https://securetoken.google.com/other-project"}])
def test_rejects_other_accounts(claims, github, change):
    claims.update(change)
    response = client.post("/github/publish", json={"readme": "x"}, headers=AUTH)
    assert response.status_code == 403
    assert github.calls == []


def test_commits_changed_readme_with_current_sha(claims, github):
    github.routes[("GET", README_PATH)] = (200, {"content": encoded("old"), "sha": "abc", "html_url": "https://github.com/octo/octo/blob/main/README.md"})
    github.routes[("PUT", README_PATH)] = (200, {"content": {"html_url": "readme-url"}, "commit": {"html_url": "commit-url"}})

    response = client.post("/github/publish", json={"readme": "# New ✨"}, headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {"readme": {"status": "updated", "url": "readme-url", "commit": "commit-url"}}
    method, path, body = github.calls[-1]
    assert (method, path, body["sha"], base64.b64decode(body["content"]).decode()) == ("PUT", README_PATH, "abc", "# New ✨")


def test_creates_readme_when_missing(claims, github):
    github.routes[("PUT", README_PATH)] = (201, {"content": {"html_url": "readme-url"}, "commit": {"html_url": "commit-url"}})
    assert client.post("/github/publish", json={"readme": "# Hi"}, headers=AUTH).json()["readme"]["status"] == "updated"
    assert "sha" not in github.calls[-1][2]


def test_skips_commit_when_readme_unchanged(claims, github):
    github.routes[("GET", README_PATH)] = (200, {"content": encoded("# Same"), "sha": "abc", "html_url": "readme-url"})
    response = client.post("/github/publish", json={"readme": "# Same"}, headers=AUTH)
    assert response.json() == {"readme": {"status": "unchanged", "url": "readme-url"}}
    assert all(method != "PUT" for method, _, _ in github.calls)


def test_missing_profile_repository_is_reported(claims, github):
    response = client.post("/github/publish", json={"readme": "# Hi"}, headers=AUTH)
    assert response.status_code == 502
    assert "octo/octo not found" in response.json()["detail"]


def test_updates_only_given_profile_fields(claims, github):
    github.routes[("PATCH", "/user")] = (200, {"html_url": "https://github.com/octo"})
    response = client.post("/github/publish", json={"profile": {"bio": "Builder", "hireable": False}}, headers=AUTH)
    assert response.json() == {"profile": {"status": "updated", "url": "https://github.com/octo"}}
    assert github.calls == [("PATCH", "/user", {"bio": "Builder", "hireable": False})]


def test_rejects_bio_over_github_limit(claims, github):
    response = client.post("/github/publish", json={"profile": {"bio": "x" * 161}}, headers=AUTH)
    assert response.status_code == 422
    assert github.calls == []


def test_github_errors_are_passed_on(claims, github):
    github.routes[("PATCH", "/user")] = (403, {"message": "Resource not accessible by personal access token"})
    response = client.post("/github/publish", json={"profile": {"bio": "x"}}, headers=AUTH)
    assert response.status_code == 502
    assert "Resource not accessible" in response.json()["detail"]


def test_cors_allows_only_configured_origins():
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization,content-type"}
    allowed = client.options("/github/publish", headers={"Origin": "https://site.example", **preflight})
    other = client.options("/github/publish", headers={"Origin": "https://evil.example", **preflight})
    assert allowed.headers.get("access-control-allow-origin") == "https://site.example"
    assert "access-control-allow-origin" not in other.headers


CRON = {"Authorization": "Bearer cron-secret"}
STALE = "Since <!--experience:2020-01-15~2021-03-20,2022-01-01~2022-06-01-->**0Y 1M**<!--/experience--> · (<!--duration:2020-01-15~2021-03-20-->0Y 0M<!--/duration-->)"


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}, AUTH])
def test_refresh_only_runs_for_the_cron_secret(github, headers):
    assert client.get("/github/refresh", headers=headers).status_code == 401
    assert github.calls == []


def test_refresh_commits_recomputed_durations(github):
    github.routes[("GET", README_PATH)] = (200, {"content": encoded(STALE), "sha": "abc", "html_url": "readme-url"})
    github.routes[("PUT", README_PATH)] = (200, {"content": {"html_url": "readme-url"}, "commit": {"html_url": "commit-url"}})

    assert client.get("/github/refresh", headers=CRON).json() == {"readme": {"status": "updated", "url": "readme-url", "commit": "commit-url"}}
    _, _, body = github.calls[-1]
    assert body["message"] == "Refresh experience durations"
    assert base64.b64decode(body["content"]).decode() == STALE.replace("**0Y 1M**", "**1Y 7M**").replace("-->0Y 0M<", "-->1Y 2M<")


def test_refresh_keeps_bio_current(github):
    readme = 'Hi<!--github-bio:{"template": "Dev with Y-M-D", "experience": [["2020-01-15", "2021-03-20"]]}-->'
    github.routes[("GET", README_PATH)] = (200, {"content": encoded(readme), "sha": "abc", "html_url": "readme-url"})
    github.routes[("PATCH", "/user")] = (200, {"html_url": "https://github.com/octo"})

    result = client.get("/github/refresh", headers=CRON).json()
    assert result["readme"]["status"] == "unchanged"
    assert ("PATCH", "/user", {"bio": "Dev with 1Y 2M"}) in github.calls


def test_refresh_without_readme(github):
    assert client.get("/github/refresh", headers=CRON).json() == {"readme": {"status": "missing"}}
