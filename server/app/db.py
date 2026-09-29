from __future__ import annotations

import sqlite3
from pathlib import Path


def connect_sqlite(database_path: Path) -> sqlite3.Connection:
    """Open a small-production SQLite connection with predictable lock handling."""
    connection = sqlite3.connect(database_path, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection
