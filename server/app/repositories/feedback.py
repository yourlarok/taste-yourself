from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.domain.models import FitFeedback


class FeedbackRepository:
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
                CREATE TABLE IF NOT EXISTS fit_feedback (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id TEXT NOT NULL,
                  product_id TEXT NOT NULL,
                  sku_id TEXT NOT NULL,
                  size_label TEXT NOT NULL,
                  outcome TEXT NOT NULL,
                  overall_fit TEXT NOT NULL,
                  area_feedback_json TEXT NOT NULL,
                  analysis_id TEXT,
                  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def add(self, feedback: FitFeedback) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO fit_feedback (
                  user_id, product_id, sku_id, size_label, outcome, overall_fit,
                  area_feedback_json, analysis_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    feedback.user_id,
                    feedback.product_id,
                    feedback.sku_id,
                    feedback.size_label,
                    feedback.outcome.value,
                    feedback.overall_fit.value,
                    json.dumps(
                        {key: value.value for key, value in feedback.area_feedback.items()},
                        ensure_ascii=False,
                    ),
                    feedback.analysis_id,
                ),
            )
            return int(cursor.lastrowid)
