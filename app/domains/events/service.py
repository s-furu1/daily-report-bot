from __future__ import annotations

import json
import sqlite3
from typing import Any

from app.domains.events.repository import insert_event


def record_event(
    conn: sqlite3.Connection, event_type: str, source: str, payload: dict[str, Any]
) -> int:
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    json.loads(payload_json)
    return insert_event(conn, event_type, source, payload_json)
