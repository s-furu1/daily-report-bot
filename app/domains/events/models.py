from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    id: int
    event_type: str
    source: str
    payload_json: str
    created_at: str
