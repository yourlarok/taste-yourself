from __future__ import annotations

import sqlite3
from pathlib import Path


class PrivacyService:
    def __init__(self, database_path: Path, media_root: Path) -> None:
        self.database_path = database_path
        self.media_root = media_root.resolve()

    def delete_user_data(self, user_id: str) -> dict[str, int]:
        media_paths: set[str] = set()
        counts: dict[str, int] = {}
        scan_ids: list[str] = []
        with sqlite3.connect(self.database_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")

            for table, column in (
                ("wardrobe_garments", "image_path"),
                ("person_images", "image_path"),
            ):
                if self._table_exists(connection, table):
                    rows = connection.execute(
                        f"SELECT {column} FROM {table} WHERE user_id = ?",  # noqa: S608
                        (user_id,),
                    ).fetchall()
                    media_paths.update(str(row[column]) for row in rows)

            if self._table_exists(connection, "body_scans"):
                scan_rows = connection.execute(
                    "SELECT id FROM body_scans WHERE user_id = ?", (user_id,)
                ).fetchall()
                scan_ids = [str(row["id"]) for row in scan_rows]
                for scan_id in scan_ids:
                    if self._table_exists(connection, "body_scan_frames"):
                        rows = connection.execute(
                            "SELECT image_path FROM body_scan_frames WHERE scan_id = ?", (scan_id,)
                        ).fetchall()
                        media_paths.update(str(row["image_path"]) for row in rows)

            if self._table_exists(connection, "experience_sessions"):
                session_rows = connection.execute(
                    "SELECT id FROM experience_sessions WHERE user_id = ?", (user_id,)
                ).fetchall()
                session_ids = [str(row["id"]) for row in session_rows]
                for session_id in session_ids:
                    if self._table_exists(connection, "tryon_results"):
                        rows = connection.execute(
                            """
                            SELECT result_path FROM tryon_results
                            WHERE experience_session_id = ?
                            """,
                            (session_id,),
                        ).fetchall()
                        media_paths.update(str(row["result_path"]) for row in rows)
                        connection.execute(
                            "DELETE FROM tryon_results WHERE experience_session_id = ?",
                            (session_id,),
                        )

            for table, identity_column in (
                ("fit_feedback", "user_id"),
                ("garment_size_charts", "user_id"),
                ("wardrobe_garments", "user_id"),
                ("person_images", "user_id"),
                ("body_scans", "user_id"),
                ("experience_sessions", "user_id"),
                ("daily_usage", "user_id"),
                ("user_fit_profiles", "user_id"),
                ("users", "id"),
            ):
                if self._table_exists(connection, table):
                    cursor = connection.execute(
                        f"DELETE FROM {table} WHERE {identity_column} = ?",  # noqa: S608
                        (user_id,),
                    )
                    counts[table] = cursor.rowcount

            if self._table_exists(connection, "body_scan_frames"):
                for scan_id in scan_ids:
                    connection.execute("DELETE FROM body_scan_frames WHERE scan_id = ?", (scan_id,))

            connection.commit()

        deleted_files = 0
        for relative_path in media_paths:
            target = (self.media_root / relative_path).resolve()
            if self.media_root in target.parents and target.is_file():
                target.unlink()
                deleted_files += 1
        counts["media_files"] = deleted_files
        return counts

    @staticmethod
    def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
        row = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
        ).fetchone()
        return row is not None
