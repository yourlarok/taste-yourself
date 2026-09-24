from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


class RetentionService:
    def __init__(self, database_path: Path, media_root: Path) -> None:
        self.database_path = database_path
        self.media_root = media_root.resolve()

    def purge(self, person_days: int, result_days: int) -> dict[str, int]:
        counts = {"person_images": 0, "tryon_results": 0, "media_files": 0}
        media_paths: list[str] = []
        now = datetime.now(UTC)
        cutoffs = {
            "person_images": (now - timedelta(days=person_days)).isoformat(),
            "tryon_results": (now - timedelta(days=result_days)).isoformat(),
        }
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            for table, path_column in (
                ("person_images", "image_path"),
                ("tryon_results", "result_path"),
            ):
                if not self._table_exists(connection, table):
                    continue
                rows = connection.execute(
                    f"SELECT {path_column} FROM {table} WHERE created_at < ?",  # noqa: S608
                    (cutoffs[table],),
                ).fetchall()
                media_paths.extend(str(row[path_column]) for row in rows)
                cursor = connection.execute(
                    f"DELETE FROM {table} WHERE created_at < ?",  # noqa: S608
                    (cutoffs[table],),
                )
                counts[table] = cursor.rowcount
            connection.commit()

        for relative_path in media_paths:
            target = (self.media_root / relative_path).resolve()
            if self.media_root in target.parents and target.is_file():
                target.unlink()
                counts["media_files"] += 1
        return counts

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        return row is not None
