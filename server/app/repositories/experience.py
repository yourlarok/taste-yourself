from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.experience import ExperienceSession


class ExperienceRepository:
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
                CREATE TABLE IF NOT EXISTS experience_sessions (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  garment_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tryon_results (
                  id TEXT PRIMARY KEY,
                  experience_session_id TEXT NOT NULL,
                  result_path TEXT NOT NULL,
                  created_at TEXT NOT NULL
                )
                """
            )

    def create(self, user_id: str, garment_id: str) -> ExperienceSession:
        session_id = str(uuid4())
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO experience_sessions (
                  id, user_id, garment_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (session_id, user_id, garment_id, now.isoformat(), now.isoformat()),
            )
        return ExperienceSession(
            id=session_id,
            user_id=user_id,
            garment_id=garment_id,
            status="active",
            created_at=now,
            updated_at=now,
        )

    def get(self, session_id: str) -> ExperienceSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM experience_sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return ExperienceSession.model_validate(dict(row)) if row else None

    def select_garment(self, session_id: str, garment_id: str) -> ExperienceSession | None:
        now = datetime.now(UTC)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE experience_sessions
                SET garment_id = ?, updated_at = ?
                WHERE id = ? AND status = 'active'
                """,
                (garment_id, now.isoformat(), session_id),
            )
        return self.get(session_id) if cursor.rowcount else None

    def add_result(self, session_id: str, result_path: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tryon_results (id, experience_session_id, result_path, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid4()), session_id, result_path, now),
            )
            connection.execute(
                "UPDATE experience_sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

    def latest_for_user(self, user_id: str) -> tuple[ExperienceSession, str | None] | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM experience_sessions
                WHERE user_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
            if row is None:
                return None
            result = connection.execute(
                """
                SELECT result_path FROM tryon_results
                WHERE experience_session_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (row["id"],),
            ).fetchone()
        return (
            ExperienceSession.model_validate(dict(row)),
            str(result["result_path"]) if result else None,
        )
