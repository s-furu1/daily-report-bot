from __future__ import annotations

from contextlib import contextmanager

from app.core.config import load_settings
from app.core.db import connect, run_migrations
from app.slack.blocks import PANEL_ACTION_IDS, server_report_panel_blocks
from app.slack.handlers import (
    handle_report_github_show,
    handle_report_jobs_show,
    handle_report_today_show,
    handle_report_week_show,
)
from app.slack.main import post_alert, register_action_handlers


def _action_ids(blocks):
    ids = set()
    for block in blocks:
        for element in block.get("elements", []):
            if "action_id" in element:
                ids.add(element["action_id"])
    return ids


def test_server_report_panel_contains_expected_action_ids():
    blocks = server_report_panel_blocks(
        today_success_rate_text="100%",
        today_commit_count_text="3",
        latest_failed_job_text="(なし)",
    )
    assert PANEL_ACTION_IDS <= _action_ids(blocks)


def test_handle_report_today_show_acks_first_then_calls_builder(tmp_path):
    order: list[str] = []

    def ack():
        order.append("ack")

    def build():
        order.append("build")
        return type("R", (), {"target_date": "2026-05-05"})()

    with connect(str(tmp_path / "s.db")) as conn:
        run_migrations(conn)
        handle_report_today_show(ack, build, conn)
        assert order == ["ack", "build"]
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "slack.report.today.show" in types


def test_handle_report_week_show_acks_first_then_calls_builder(tmp_path):
    order: list[str] = []

    def ack():
        order.append("ack")

    def build():
        order.append("build")
        return type("R", (), {"target_week_start": "2026-05-04"})()

    with connect(str(tmp_path / "s.db")) as conn:
        run_migrations(conn)
        handle_report_week_show(ack, build, conn)
        assert order == ["ack", "build"]
        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "slack.report.week.show" in types


def test_handle_report_jobs_and_github_show_ack_and_record(tmp_path):
    with connect(str(tmp_path / "s.db")) as conn:
        run_migrations(conn)

        order_jobs: list[str] = []
        handle_report_jobs_show(lambda: order_jobs.append("ack"), conn)
        assert order_jobs == ["ack"]

        order_gh: list[str] = []
        handle_report_github_show(lambda: order_gh.append("ack"), conn)
        assert order_gh == ["ack"]

        types = [
            row["event_type"]
            for row in conn.execute("SELECT event_type FROM report_events").fetchall()
        ]
        assert "slack.report.jobs.show" in types
        assert "slack.report.github.show" in types


class FakeApp:
    def __init__(self):
        self.registered: dict[str, object] = {}

    def action(self, action_id: str):
        def decorator(fn):
            self.registered[action_id] = fn
            return fn

        return decorator


def _wired_db_ctx(tmp_path):
    @contextmanager
    def db_ctx():
        with connect(str(tmp_path / "wired.db")) as conn:
            run_migrations(conn)
            yield conn

    return db_ctx


def test_register_action_handlers_covers_all_panel_action_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "x.db"))
    settings = load_settings()
    fake_app = FakeApp()
    register_action_handlers(fake_app, settings)
    assert PANEL_ACTION_IDS <= set(fake_app.registered)


def test_register_action_handlers_today_invokes_factory(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "x.db"))
    settings = load_settings()
    fake_app = FakeApp()

    called = {"flag": False}

    def fake_today(conn):
        called["flag"] = True
        return type("R", (), {"target_date": "2026-05-05"})()

    register_action_handlers(
        fake_app,
        settings,
        today_report_factory=fake_today,
        db_context_factory=_wired_db_ctx(tmp_path),
    )
    order: list[str] = []

    def ack():
        order.append("ack")

    fake_app.registered["report.today.show"](ack=ack, body={})
    assert order[0] == "ack"
    assert called["flag"] is True


def test_register_action_handlers_week_invokes_factory(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "x.db"))
    settings = load_settings()
    fake_app = FakeApp()

    called = {"flag": False}

    def fake_weekly(conn):
        called["flag"] = True
        return type("R", (), {"target_week_start": "2026-05-04"})()

    register_action_handlers(
        fake_app,
        settings,
        weekly_report_factory=fake_weekly,
        db_context_factory=_wired_db_ctx(tmp_path),
    )
    order: list[str] = []

    def ack():
        order.append("ack")

    fake_app.registered["report.week.show"](ack=ack, body={})
    assert order[0] == "ack"
    assert called["flag"] is True


def test_post_alert_skips_when_channel_missing():
    posted: list[tuple[str, str]] = []

    def client_post(channel, text):
        posted.append((channel, text))

    assert post_alert(client_post, None, "hi") is False
    assert posted == []


def test_post_alert_swallows_exception():
    def client_post(channel, text):
        raise RuntimeError("boom")

    assert post_alert(client_post, "C123", "hi") is False
