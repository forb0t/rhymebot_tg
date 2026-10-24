"""
SQLite-хранилище подписок на рассылку стихов.
"""

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Формат времени в базе: всегда UTC
TS_FORMAT = "%Y-%m-%d %H:%M:%S"


def data_dir() -> Path:
    path = Path(os.environ.get("RHYMES_DATA_DIR", ".")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def to_ts(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(TS_FORMAT)


def from_ts(ts: str) -> datetime:
    return datetime.strptime(ts, TS_FORMAT).replace(tzinfo=timezone.utc)


class Storage:
    def __init__(self, path: Path | str | None = None) -> None:
        self.conn = sqlite3.connect(str(path or data_dir() / "rhymes.db"))
        self.conn.row_factory = sqlite3.Row
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    chat_id INTEGER PRIMARY KEY,
                    every_days INTEGER NOT NULL DEFAULT 1,
                    hour INTEGER NOT NULL DEFAULT 9,
                    enabled INTEGER NOT NULL DEFAULT 0,
                    next_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def get(self, chat_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM subscriptions WHERE chat_id = ?", (chat_id,)).fetchone()

    def save(self, chat_id: int, every_days: int, hour: int, enabled: bool, next_at: datetime | None) -> None:
        with self.conn:
            self.conn.execute("""
                INSERT INTO subscriptions (chat_id, every_days, hour, enabled, next_at) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT (chat_id) DO UPDATE SET
                    every_days = excluded.every_days, hour = excluded.hour,
                    enabled = excluded.enabled, next_at = excluded.next_at
            """, (chat_id, every_days, hour, int(enabled), to_ts(next_at) if next_at else None))

    def set_next(self, chat_id: int, next_at: datetime) -> None:
        with self.conn:
            self.conn.execute("UPDATE subscriptions SET next_at = ? WHERE chat_id = ?", (to_ts(next_at), chat_id))

    def due(self, now: datetime) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM subscriptions WHERE enabled = 1 AND next_at <= ? ORDER BY next_at", (to_ts(now),),
        ).fetchall()

    def delete(self, chat_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM subscriptions WHERE chat_id = ?", (chat_id,))
