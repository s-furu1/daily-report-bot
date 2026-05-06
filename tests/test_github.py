from __future__ import annotations

import pytest

from app.core.db import connect, run_migrations
from app.domains.reports.service import build_daily_report, collect_commit_counts
from app.github.client import GitHubClient, GitHubError
from app.github.repositories import resolve_repositories
from app.metrics.server import ServerMetrics


class FakeGitHubClient:
    def __init__(self, mapping=None, error_repos=()):
        self.mapping = mapping or {}
        self.error_repos = set(error_repos)
        self.calls: list[tuple[str, str | None, str | None]] = []
        self.repository_error: GitHubError | None = None
        self.repositories: tuple[str, ...] = tuple(self.mapping)

    def list_authenticated_user_repositories(self):
        if self.repository_error is not None:
            raise self.repository_error
        return self.repositories

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


class FakeUrlopenResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


def test_github_client_fetches_all_authenticated_user_repositories(monkeypatch):
    def fake_urlopen(request, timeout):
        assert timeout == 30
        assert request.full_url.startswith("https://api.github.com/user/repos?")
        assert "visibility=all" in request.full_url
        assert "affiliation=owner%2Ccollaborator%2Corganization_member" in request.full_url
        return FakeUrlopenResponse(
            b"""[
                {"full_name": "example-owner/app", "archived": false, "fork": false},
                {"full_name": "example-owner/private", "private": true},
                {"full_name": "example-owner/archived", "archived": true},
                {"full_name": "example-owner/forked", "fork": true}
            ]"""
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    repos = GitHubClient("test-token").list_authenticated_user_repositories()
    assert repos == (
        "example-owner/app",
        "example-owner/private",
        "example-owner/archived",
        "example-owner/forked",
    )


def test_github_client_fetches_repositories_with_pagination(monkeypatch):
    responses = {
        "page=1": b"""[
            {"full_name": "example-owner/one"},
            {"full_name": "example-owner/two"}
        ]""",
        "page=2": b"""[
            {"full_name": "example-owner/three"}
        ]""",
    }
    requested_urls: list[str] = []

    def fake_urlopen(request, timeout):
        requested_urls.append(request.full_url)
        for marker, body in responses.items():
            if marker in request.full_url:
                return FakeUrlopenResponse(body)
        raise AssertionError(f"unexpected URL: {request.full_url}")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    repos = GitHubClient("test-token").list_authenticated_user_repositories(per_page=2)
    assert repos == (
        "example-owner/one",
        "example-owner/two",
        "example-owner/three",
    )
    assert len(requested_urls) == 2


def test_resolved_repositories_are_used_for_commit_counts(tmp_path):
    with connect(str(tmp_path / "g.db")) as conn:
        run_migrations(conn)
        client = FakeGitHubClient(
            {
                "example-owner/app": [{"sha": "a"}],
                "example-owner/private": [{"sha": "b"}, {"sha": "c"}],
                "example-owner/archived": [],
                "example-owner/forked": [{"sha": "d"}],
            }
        )
        repos = resolve_repositories(conn, client)
        report = build_daily_report(
            conn,
            github_client=client,
            repositories=repos,
            metrics=ServerMetrics(disk=None, memory=None, load_average=None),
            target_date="2026-05-05",
        )

        assert dict(report.commit_counts) == {
            "example-owner/app": 1,
            "example-owner/private": 2,
            "example-owner/archived": 0,
            "example-owner/forked": 1,
        }
        assert [call[0] for call in client.calls] == list(repos)


def test_repository_list_failure_records_event_and_skips(tmp_path):
    with connect(str(tmp_path / "g.db")) as conn:
        run_migrations(conn)
        client = FakeGitHubClient()
        client.repository_error = GitHubError("forced repository error")

        assert resolve_repositories(conn, client) == ()
        rows = conn.execute(
            "SELECT event_type, payload_json FROM report_events"
        ).fetchall()
        assert [row["event_type"] for row in rows] == ["github.repositories.failed"]
        assert "forced repository error" in rows[0]["payload_json"]


def test_repository_resolution_without_token_records_failed_event(tmp_path):
    with connect(str(tmp_path / "g.db")) as conn:
        run_migrations(conn)
        client = GitHubClient(token=None)

        assert resolve_repositories(conn, client) == ()
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert types == ["github.repositories.failed"]
