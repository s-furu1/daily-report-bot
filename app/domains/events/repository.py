from __future__ import annotations

import sqlite3

from app.core.time import utc_now_iso


def insert_event(
    conn: sqlite3.Connection, event_type: str, source: str, payload_json: str
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO report_events (event_type, source, payload_json, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (event_type, source, payload_json, utc_now_iso()),
    )
    conn.commit()
    return int(cursor.lastrowid)


def list_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM report_events ORDER BY id DESC").fetchall()
