from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_run_and_log():
    spec = importlib.util.spec_from_file_location(
        "run_and_log_script", ROOT / "scripts" / "run-and-log.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run_and_log = _load_run_and_log()


def test_run_records_success_command(tmp_path):
    db_path = tmp_path / "rl.db"
    rc = run_and_log.run(
        "echo-job",
        [sys.executable, "-c", "print('hello')"],
        db_path=str(db_path),
    )
    assert rc == 0
    from app.core.db import connect

    with connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT job_name, status, exit_code, stdout_tail FROM job_runs"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["job_name"] == "echo-job"
    assert rows[0]["status"] == "success"
    assert rows[0]["exit_code"] == 0
    assert "hello" in (rows[0]["stdout_tail"] or "")


def test_run_records_failed_command(tmp_path):
    db_path = tmp_path / "rl.db"
    rc = run_and_log.run(
        "fail-job",
        [
            sys.executable,
            "-c",
            "import sys; sys.stderr.write('oops'); sys.exit(3)",
        ],
        db_path=str(db_path),
    )
    assert rc == 3
    from app.core.db import connect

    with connect(str(db_path)) as conn:
        rows = conn.execute(
            "SELECT status, exit_code, stderr_tail FROM job_runs"
        ).fetchall()
    assert rows[0]["status"] == "failed"
    assert rows[0]["exit_code"] == 3
    assert "oops" in (rows[0]["stderr_tail"] or "")


def test_run_records_filenotfound_as_failed(tmp_path):
    db_path = tmp_path / "rl.db"
    rc = run_and_log.run(
        "missing-cmd",
        ["/this/does/not/exist-xyz-daily-report"],
        db_path=str(db_path),
    )
    assert rc == 127
    from app.core.db import connect

    with connect(str(db_path)) as conn:
        rows = conn.execute("SELECT status, exit_code FROM job_runs").fetchall()
    assert rows[0]["status"] == "failed"
    assert rows[0]["exit_code"] == 127


def test_parse_args_requires_separator():
    import pytest

    with pytest.raises(SystemExit):
        run_and_log.parse_args(["job-name"])


def test_parse_args_returns_job_and_command():
    job, cmd = run_and_log.parse_args(
        ["backup-life-db", "--", "/scripts/backup-life-db.sh"]
    )
    assert job == "backup-life-db"
    assert cmd == ["/scripts/backup-life-db.sh"]
