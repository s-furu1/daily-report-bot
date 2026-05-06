from __future__ import annotations

from app.main import main


def test_main_starts_with_temp_db(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "daily-report.db"))
    monkeypatch.delenv("DAILY_REPORT_ENABLE_SLACK", raising=False)
    monkeypatch.delenv("DAILY_REPORT_ENABLE_WORKER", raising=False)
    assert main() == 0
    assert "daily-report-bot started" in capsys.readouterr().out
