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
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "daily-report-bot/0.1",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise GitHubError(f"GitHub request failed for {repo}: {exc}") from exc
        if not isinstance(body, list):
            raise GitHubError(f"unexpected GitHub response for {repo}")
        return body
