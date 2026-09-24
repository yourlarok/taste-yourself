from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


class FitProfileRepository:
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
                CREATE TABLE IF NOT EXISTS user_fit_profiles (
                  user_id TEXT PRIMARY KEY,
                  source_scan_id TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  measurements_json TEXT NOT NULL,
                  uncertainty_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )

    def save(
        self,
        user_id: str,
        source_scan_id: str,
        provider: str,
        measurements_cm: dict[str, float],
        uncertainty_cm: dict[str, float],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_fit_profiles (
                  user_id, source_scan_id, provider, measurements_json,
                  uncertainty_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  source_scan_id = excluded.source_scan_id,
                  provider = excluded.provider,
                  measurements_json = excluded.measurements_json,
                  uncertainty_json = excluded.uncertainty_json,
                  updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    source_scan_id,
                    provider,
                    json.dumps(measurements_cm, ensure_ascii=False),
                    json.dumps(uncertainty_cm, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )

    def get(self, user_id: str) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_fit_profiles WHERE user_id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return {
            "user_id": str(row["user_id"]),
            "source_scan_id": str(row["source_scan_id"]),
            "provider": str(row["provider"]),
            "measurements_cm": json.loads(row["measurements_json"]),
            "measurement_uncertainty_cm": json.loads(row["uncertainty_json"]),
            "updated_at": str(row["updated_at"]),
        }

    def delete(self, user_id: str) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                "DELETE FROM user_fit_profiles WHERE user_id = ?", (user_id,)
            )
        return cursor.rowcount
