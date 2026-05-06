from __future__ import annotations

import json

from app.core.db import connect, run_migrations
from app.domains.events.service import record_event


def test_record_event_writes_to_report_events(tmp_path):
    with connect(str(tmp_path / "x.db")) as conn:
        run_migrations(conn)
        record_event(conn, "test.event", "test", {"k": "v", "n": 1})
        row = conn.execute(
            "SELECT event_type, source, payload_json FROM report_events"
        ).fetchone()
        assert row["event_type"] == "test.event"
        assert row["source"] == "test"
        assert json.loads(row["payload_json"]) == {"k": "v", "n": 1}
