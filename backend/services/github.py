"""Publishing rules for the owner's GitHub profile: the README in <login>/<login> and the profile details."""

from datetime import date

from backend.core.errors import UpstreamError
from backend.models.github import BIO_LIMIT, Change, GitHubResult, PublishRequest, ReadmeFile
from backend.repositories.github import GitHubRepository
from backend.services.experience import bio_from_readme, refresh_readme

COMMIT_MESSAGE = "Update profile README from the portfolio admin"
REFRESH_MESSAGE = "Refresh experience durations"


class GitHubProfileService:
    def __init__(self, github: GitHubRepository):
        self.github = github
        self._user: dict | None = None

    async def _account(self) -> dict:
        """The token's account, fetched once per request."""
        if self._user is None:
            self._user = await self.github.user()
        return self._user

    async def _profile_repo(self) -> str:
        login = (await self._account())["login"]
        return f"{login}/{login}"

    async def publish(self, request: PublishRequest) -> GitHubResult:
        """Publishes whichever of `readme` and `profile` the request includes."""
        result = GitHubResult()
        if request.readme is not None:
            repo = await self._profile_repo()
            result.readme = await self._write_readme(repo, await self.github.readme(repo), request.readme, COMMIT_MESSAGE)
        if request.profile is not None:
            result.profile = await self._update_profile(request.profile.model_dump(exclude_none=True))
        return result

    async def refresh(self, today: date) -> GitHubResult:
        """Recomputes the experience durations in the published README and bio (see experience.py).

        Reads only the README on GitHub, so it never publishes edits the admin has not published.
        """
        repo = await self._profile_repo()
        current = await self.github.readme(repo)
        if current is None:
            return GitHubResult(readme=Change(status="missing"))
        markdown = refresh_readme(current.text, today)
        result = GitHubResult(readme=await self._write_readme(repo, current, markdown, REFRESH_MESSAGE))

        bio = bio_from_readme(markdown, today)
        if bio is not None and len(bio) <= BIO_LIMIT:
            unchanged = bio == ((await self._account()).get("bio") or "")
            result.profile = Change(status="unchanged") if unchanged else await self._update_profile({"bio": bio})
        return result

    async def _write_readme(self, repo: str, current: ReadmeFile | None, markdown: str, message: str) -> Change:
        """Commits README.md to `repo`, unless it already has this content."""
        if current and current.text == markdown:
            return Change(status="unchanged", url=current.url)

        written = await self.github.put_readme(repo, markdown, message, current.sha if current else None)
        if written is None:
            # GitHub answers 404, not 403, when the token may not write to a repository. A public repository is readable
            # by any token, so a README we could read means the repository exists and the token lacks write access.
            if current:
                raise UpstreamError(
                    f"GITHUB_TOKEN cannot write to {repo}: in the fine-grained token, add {repo} under "
                    "Repository access and set Contents to Read and write"
                )
            raise UpstreamError(
                f"GitHub returned 404 for {repo}: create that repository for a profile README, or give GITHUB_TOKEN "
                "access to it (Repository access, Contents: Read and write)"
            )
        return Change(status="updated", url=written["content"]["html_url"], commit=written["commit"]["html_url"])

    async def _update_profile(self, fields: dict) -> Change:
        user = await self.github.update_user(fields)
        return Change(status="updated", url=user["html_url"])
