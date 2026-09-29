import sqlite3
from pathlib import Path

from scripts.backup_sqlite import create_backup


def test_create_backup_is_consistent(tmp_path: Path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('cat-mirror')")

    destination = create_backup(source, tmp_path / "backups")

    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("cat-mirror",)
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
