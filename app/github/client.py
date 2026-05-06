from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class GitHubError(RuntimeError):
    pass


class GitHubClient:
    def __init__(
        self,
        token: str | None,
        base_url: str = "https://api.github.com",
        timeout: int = 30,
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "daily-report-bot/0.1",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _get_json(self, url: str, *, error_context: str):
        request = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise GitHubError(
                f"GitHub request failed for {error_context}: {exc}"
            ) from exc
        return body

    def list_commits(
        self,
        repo: str,
        *,
        since_iso: str | None = None,
        until_iso: str | None = None,
        per_page: int = 100,
    ) -> list[dict]:
        if not self.token:
            raise GitHubError("GITHUB_TOKEN is not set")
        params: list[tuple[str, str]] = []
        if since_iso:
            params.append(("since", since_iso))
        if until_iso:
            params.append(("until", until_iso))
        params.append(("per_page", str(per_page)))
        url = f"{self.base_url}/repos/{repo}/commits?" + urllib.parse.urlencode(params)
        body = self._get_json(url, error_context=repo)
        if not isinstance(body, list):
            raise GitHubError(f"unexpected GitHub response for {repo}")
        return body

    def list_authenticated_user_repositories(
        self, *, per_page: int = 100
    ) -> tuple[str, ...]:
        if not self.token:
            raise GitHubError("GITHUB_TOKEN is not set")

        repos: list[dict] = []
        page = 1
        while True:
            params = urllib.parse.urlencode(
                {
                    "visibility": "all",
                    "affiliation": "owner,collaborator,organization_member",
                    "per_page": str(per_page),
                    "page": str(page),
                }
            )
            url = f"{self.base_url}/user/repos?{params}"
            body = self._get_json(url, error_context="authenticated user repositories")
            if not isinstance(body, list):
                raise GitHubError("unexpected GitHub repository response")
            repos.extend(body)
            if len(body) < per_page:
                break
            page += 1

        names: list[str] = []
        for repo in repos:
            if not isinstance(repo, dict):
                raise GitHubError("unexpected GitHub repository response")
            full_name = repo.get("full_name")
            if isinstance(full_name, str) and full_name:
                names.append(full_name)
        return tuple(names)
