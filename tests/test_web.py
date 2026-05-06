from __future__ import annotations

from fastapi.testclient import TestClient

from app.web.main import create_app


def test_healthz_returns_200(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "daily-report.db"))
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_today_report_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "daily-report.db"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    response = TestClient(create_app()).get("/internal/reports/today")

    assert response.status_code == 200
    assert response.json()["github"]["status"] == "skipped"


def test_week_report_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "daily-report.db"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    response = TestClient(create_app()).get("/internal/reports/week")

    assert response.status_code == 200
    assert "text" in response.json()


def test_jobs_report_endpoint(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "daily-report.db"))
    response = TestClient(create_app()).get("/internal/reports/jobs")

    assert response.status_code == 200
    assert response.json()["jobs"] == []


def test_github_report_endpoint_without_token(monkeypatch, tmp_path):
    monkeypatch.setenv("DAILY_REPORT_DB_PATH", str(tmp_path / "daily-report.db"))
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    response = TestClient(create_app()).get("/internal/reports/github")

    assert response.status_code == 200
    assert response.json()["github"]["status"] == "skipped"
