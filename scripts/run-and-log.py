"""Wrap a command and log its result into job_runs.

Usage:
    python scripts/run-and-log.py <job_name> -- <command> [args...]
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.db import connect, run_migrations  # noqa: E402
from app.core.time import utc_now_iso  # noqa: E402
from app.domains.jobs.service import record_job_run  # noqa: E402


DEFAULT_TAIL_LIMIT = 4000
USAGE = "usage: run-and-log.py <job_name> -- <command> [args...]"


def parse_args(argv: list[str]) -> tuple[str, list[str]]:
    if "--" not in argv:
        raise SystemExit(USAGE)
    sep = argv.index("--")
    head = argv[:sep]
    tail = argv[sep + 1 :]
    if len(head) != 1 or not tail:
        raise SystemExit(USAGE)
    return head[0], tail


def run(
    job_name: str,
    command: list[str],
    *,
    db_path: str | None = None,
    timeout: int | None = None,
    max_tail: int = DEFAULT_TAIL_LIMIT,
) -> int:
    resolved_db_path = (
        db_path or os.getenv("DAILY_REPORT_DB_PATH", "/data/daily-report.db")
    )
    started_at = utc_now_iso()
    started_monotonic = time.monotonic()
    status = "success"
    exit_code: int | None = 0
    stdout = ""
    stderr = ""

    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        exit_code = int(proc.returncode)
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        if exit_code != 0:
            status = "failed"
    except subprocess.TimeoutExpired as exc:
        status = "timeout"
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
    except FileNotFoundError as exc:
        status = "failed"
        exit_code = 127
        stderr = str(exc)

    duration_seconds = int(time.monotonic() - started_monotonic)
    finished_at = utc_now_iso()

    with connect(resolved_db_path) as conn:
        run_migrations(conn)
        record_job_run(
            conn,
            job_name=job_name,
            started_at=started_at,
            finished_at=finished_at,
            status=status,
            exit_code=exit_code,
            duration_seconds=duration_seconds,
            stdout_tail=_tail(stdout, max_tail),
            stderr_tail=_tail(stderr, max_tail),
        )

    if status == "success":
        return 0
    if exit_code is None:
        return 124
    return exit_code


def _tail(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def main(argv: list[str]) -> int:
    job_name, command = parse_args(argv)
    return run(job_name, command)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
