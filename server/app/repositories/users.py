from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


class UserRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                  id TEXT PRIMARY KEY,
                  wechat_openid TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL,
                  last_login_at TEXT NOT NULL
                )
                """
            )

    def get_or_create_by_openid(self, openid: str) -> str:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM users WHERE wechat_openid = ?", (openid,)
            ).fetchone()
            if row:
                connection.execute(
                    "UPDATE users SET last_login_at = ? WHERE id = ?", (now, row["id"])
                )
                return str(row["id"])

            user_id = str(uuid4())
            connection.execute(
                """
                INSERT INTO users (id, wechat_openid, created_at, last_login_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, openid, now, now),
            )
            return user_id

    def exists(self, user_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
        return row is not None
