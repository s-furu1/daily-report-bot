from __future__ import annotations

from app.domains.events.service import record_event
from app.github.client import GitHubError


def resolve_repositories(conn, github_client) -> tuple[str, ...]:
    try:
        return github_client.list_authenticated_user_repositories()
    except GitHubError as exc:
        record_event(
            conn,
            "github.repositories.failed",
            "github",
            {"error": str(exc)},
        )
        return ()
