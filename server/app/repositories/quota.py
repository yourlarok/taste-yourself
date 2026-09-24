from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class QuotaRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_usage (
                  user_id TEXT NOT NULL,
                  usage_date TEXT NOT NULL,
                  static_count INTEGER NOT NULL DEFAULT 0,
                  realtime_count INTEGER NOT NULL DEFAULT 0,
                  PRIMARY KEY (user_id, usage_date)
                )
                """
            )

    def consume(self, user_id: str, kind: str, limit: int) -> bool:
        if kind not in {"static", "realtime"}:
            raise ValueError("invalid_quota_kind")
        column = f"{kind}_count"
        usage_date = datetime.now(UTC).date().isoformat()
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                INSERT OR IGNORE INTO daily_usage (user_id, usage_date)
                VALUES (?, ?)
                """,
                (user_id, usage_date),
            )
            row = connection.execute(
                f"SELECT {column} FROM daily_usage WHERE user_id = ? AND usage_date = ?",  # noqa: S608
                (user_id, usage_date),
            ).fetchone()
            if int(row[column]) >= limit:
                connection.rollback()
                return False
            connection.execute(
                f"UPDATE daily_usage SET {column} = {column} + 1 "  # noqa: S608
                "WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            )
            connection.commit()
            return True

    def refund(self, user_id: str, kind: str) -> None:
        if kind not in {"static", "realtime"}:
            raise ValueError("invalid_quota_kind")
        column = f"{kind}_count"
        usage_date = datetime.now(UTC).date().isoformat()
        with self._connect() as connection:
            connection.execute(
                f"UPDATE daily_usage SET {column} = MAX(0, {column} - 1) "  # noqa: S608
                "WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            )

    def get(self, user_id: str) -> dict[str, int]:
        usage_date = datetime.now(UTC).date().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT static_count, realtime_count FROM daily_usage
                WHERE user_id = ? AND usage_date = ?
                """,
                (user_id, usage_date),
            ).fetchone()
        return {
            "static_count": int(row["static_count"]) if row else 0,
            "realtime_count": int(row["realtime_count"]) if row else 0,
        }
