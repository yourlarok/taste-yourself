from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.db import connect_sqlite


class MirrorRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return connect_sqlite(self.database_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS mirror_conversations (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mirror_messages (
                  id TEXT PRIMARY KEY,
                  conversation_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  role TEXT NOT NULL,
                  content TEXT NOT NULL,
                  intent TEXT,
                  action_json TEXT NOT NULL DEFAULT '{}',
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mirror_messages_conversation
                  ON mirror_messages(conversation_id, created_at);
                CREATE TABLE IF NOT EXISTS cat_cards (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  family TEXT NOT NULL,
                  cat_type TEXT NOT NULL,
                  title TEXT NOT NULL,
                  subtitle TEXT NOT NULL,
                  body TEXT NOT NULL,
                  palette TEXT NOT NULL,
                  image_key TEXT NOT NULL,
                  source_id TEXT NOT NULL,
                  collected_at TEXT NOT NULL,
                  UNIQUE(user_id, family, source_id)
                );
                CREATE TABLE IF NOT EXISTS wellbeing_assessments (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  answers_json TEXT NOT NULL,
                  contributors_json TEXT NOT NULL,
                  score INTEGER NOT NULL,
                  state TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS fun_face_assessments (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  usage_date TEXT NOT NULL,
                  result_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  UNIQUE(user_id, usage_date)
                );
                """
            )

    def create_conversation(self, user_id: str) -> dict:
        conversation_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO mirror_conversations (id, user_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (conversation_id, user_id, now, now),
            )
        return {"id": conversation_id, "created_at": now}

    def owns_conversation(self, conversation_id: str, user_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM mirror_conversations WHERE id = ? AND user_id = ?",
                (conversation_id, user_id),
            ).fetchone()
        return row is not None

    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        role: str,
        content: str,
        intent: str | None = None,
        action: dict | None = None,
    ) -> dict:
        message_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO mirror_messages (
                  id, conversation_id, user_id, role, content, intent, action_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    user_id,
                    role,
                    content,
                    intent,
                    json.dumps(action or {}, ensure_ascii=False),
                    now,
                ),
            )
            connection.execute(
                "UPDATE mirror_conversations SET updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )
        return {"id": message_id, "created_at": now}

    def recent_messages(self, conversation_id: str, limit: int = 12) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content FROM mirror_messages
                WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?
                """,
                (conversation_id, limit),
            ).fetchall()
        return [
            {"role": str(row["role"]), "content": str(row["content"])} for row in reversed(rows)
        ]

    def face_available_today(self, user_id: str) -> bool:
        usage_date = datetime.now(UTC).date().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM fun_face_assessments WHERE user_id = ? AND usage_date = ?",
                (user_id, usage_date),
            ).fetchone()
        return row is None

    def save_fun_face(self, user_id: str, result: dict) -> tuple[str, str]:
        assessment_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        usage_date = datetime.now(UTC).date().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO fun_face_assessments (
                  id, user_id, usage_date, result_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    user_id,
                    usage_date,
                    json.dumps(result, ensure_ascii=False),
                    now,
                ),
            )
        return assessment_id, now

    def save_wellbeing(
        self,
        user_id: str,
        answers: list[int],
        contributors: list[str],
        score: int,
        state: str,
        result: dict,
    ) -> tuple[str, str]:
        assessment_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wellbeing_assessments (
                  id, user_id, answers_json, contributors_json, score, state,
                  result_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assessment_id,
                    user_id,
                    json.dumps(answers),
                    json.dumps(contributors),
                    score,
                    state,
                    json.dumps(result, ensure_ascii=False),
                    now,
                ),
            )
        return assessment_id, now

    def collect_card(self, user_id: str, source_id: str, card: dict) -> dict:
        card_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR IGNORE INTO cat_cards (
                  id, user_id, family, cat_type, title, subtitle, body, palette,
                  image_key, source_id, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    card_id,
                    user_id,
                    card["family"],
                    card["cat_type"],
                    card["title"],
                    card["subtitle"],
                    card["body"],
                    card["palette"],
                    card["image_key"],
                    source_id,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM cat_cards WHERE user_id = ? AND family = ? AND source_id = ?",
                (user_id, card["family"], source_id),
            ).fetchone()
        assert row is not None
        return dict(row)

    def list_cards(self, user_id: str) -> list[dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM cat_cards WHERE user_id = ? ORDER BY collected_at DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]
