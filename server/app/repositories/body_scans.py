from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.experience import BodyScanResult


class BodyScanRepository:
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
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS body_scans (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  experience_session_id TEXT NOT NULL,
                  status TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS body_scan_frames (
                  scan_id TEXT NOT NULL,
                  angle TEXT NOT NULL,
                  image_path TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY (scan_id, angle)
                );
                """
            )

    def create(self, user_id: str, experience_session_id: str, provider: str) -> BodyScanResult:
        scan_id = str(uuid4())
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO body_scans (
                  id, user_id, experience_session_id, status, provider, created_at, updated_at
                ) VALUES (?, ?, ?, 'created', ?, ?, ?)
                """,
                (scan_id, user_id, experience_session_id, provider, now, now),
            )
        return BodyScanResult(
            id=scan_id,
            experience_session_id=experience_session_id,
            status="created",
            provider=provider,
            notice="扫描任务已创建，请按顺序上传正面和侧面画面。",
        )

    def get_owner(self, scan_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id FROM body_scans WHERE id = ?", (scan_id,)
            ).fetchone()
        return str(row["user_id"]) if row else None

    def get_experience_session_id(self, scan_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT experience_session_id FROM body_scans WHERE id = ?", (scan_id,)
            ).fetchone()
        return str(row["experience_session_id"]) if row else None

    def add_frame(self, scan_id: str, angle: str, image_path: str) -> None:
        now = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO body_scan_frames (scan_id, angle, image_path, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scan_id, angle) DO UPDATE SET
                  image_path = excluded.image_path,
                  created_at = excluded.created_at
                """,
                (scan_id, angle, image_path, now),
            )
            connection.execute(
                "UPDATE body_scans SET status = 'uploading', updated_at = ? WHERE id = ?",
                (now, scan_id),
            )

    def frames(self, scan_id: str, media_root: Path) -> dict[str, Path]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT angle, image_path FROM body_scan_frames WHERE scan_id = ?", (scan_id,)
            ).fetchall()
        return {str(row["angle"]): media_root / str(row["image_path"]) for row in rows}

    def set_status(self, scan_id: str, status: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE body_scans SET status = ?, updated_at = ? WHERE id = ?",
                (status, datetime.now(UTC).isoformat(), scan_id),
            )

    def delete_frames(self, scan_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT image_path FROM body_scan_frames WHERE scan_id = ?", (scan_id,)
            ).fetchall()
            connection.execute("DELETE FROM body_scan_frames WHERE scan_id = ?", (scan_id,))
        return [str(row["image_path"]) for row in rows]
