"""
NebulaLive V1 - State & Dedup Deposu

İki şeyi tutar:
1. Her izlenen maçın en son bilinen skorunu (değişiklik = potansiyel gol)
2. Daha önce yayınlanmış event id'lerini (aynı golü iki kere paylaşmamak için)

SQLite kullanıyoruz çünkü V1 için yeterli, ekstra servis gerektirmiyor.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Optional

from config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS match_state (
    match_id TEXT PRIMARY KEY,
    last_score TEXT,
    last_minute TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS published_events (
    event_id TEXT PRIMARY KEY,
    match_id TEXT,
    event_type TEXT,
    tweet_id TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def get_last_score(match_id: str) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_score FROM match_state WHERE match_id = ?", (match_id,)
        ).fetchone()
        return row[0] if row else None


def set_last_score(match_id: str, score: str, minute: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO match_state (match_id, last_score, last_minute)
            VALUES (?, ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                last_score = excluded.last_score,
                last_minute = excluded.last_minute,
                updated_at = datetime('now')
            """,
            (match_id, score, minute),
        )


def is_event_published(event_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM published_events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return row is not None


def mark_event_published(
    event_id: str, match_id: str, event_type: str, tweet_id: Optional[str] = None
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO published_events (event_id, match_id, event_type, tweet_id)
            VALUES (?, ?, ?, ?)
            """,
            (event_id, match_id, event_type, tweet_id),
        )
