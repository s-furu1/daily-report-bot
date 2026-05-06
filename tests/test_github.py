from __future__ import annotations

import pytest

from app.core.db import connect, run_migrations
from app.domains.reports.service import collect_commit_counts
from app.github.client import GitHubClient, GitHubError


class FakeGitHubClient:
    def __init__(self, mapping=None, error_repos=()):
        self.mapping = mapping or {}
        self.error_repos = set(error_repos)
        self.calls: list[tuple[str, str | None, str | None]] = []

    def list_commits(self, repo, *, since_iso=None, until_iso=None, **_):
        self.calls.append((repo, since_iso, until_iso))
        if repo in self.error_repos:
            raise GitHubError(f"forced error for {repo}")
        return list(self.mapping.get(repo, []))


def test_collect_commit_counts_aggregates_via_mock_client(tmp_path):
    with connect(str(tmp_path / "g.db")) as conn:
        run_migrations(conn)
        client = FakeGitHubClient(
            mapping={
                "example-owner/life-bot": [{"sha": "a"}, {"sha": "b"}],
                "example-owner/ai-feed-bot": [{"sha": "c"}],
            }
        )
        counts = collect_commit_counts(
            conn,
            client,
            ("example-owner/life-bot", "example-owner/ai-feed-bot"),
            "2026-05-05T00:00:00+00:00",
            "2026-05-06T00:00:00+00:00",
        )
        assert dict(counts) == {
            "example-owner/life-bot": 2,
            "example-owner/ai-feed-bot": 1,
        }


def test_collect_commit_counts_records_event_on_error(tmp_path):
    with connect(str(tmp_path / "g.db")) as conn:
        run_migrations(conn)
        client = FakeGitHubClient(
            mapping={"ok/repo": [{"sha": "x"}]},
            error_repos={"bad/repo"},
        )
        counts = collect_commit_counts(
            conn,
            client,
            ("ok/repo", "bad/repo"),
            "2026-05-05T00:00:00+00:00",
            "2026-05-06T00:00:00+00:00",
        )
        assert dict(counts) == {"ok/repo": 1, "bad/repo": None}
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "github.commit.failed" in types


def test_github_client_without_token_raises_clear_error():
    client = GitHubClient(token=None)
    with pytest.raises(GitHubError):
        client.list_commits("any/repo")


def test_github_token_unset_does_not_crash_aggregation(tmp_path):
    with connect(str(tmp_path / "g.db")) as conn:
        run_migrations(conn)
        client = GitHubClient(token=None)
        counts = collect_commit_counts(
            conn,
            client,
            ("a/b",),
            "2026-05-05T00:00:00+00:00",
            "2026-05-06T00:00:00+00:00",
        )
        assert dict(counts) == {"a/b": None}
