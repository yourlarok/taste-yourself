from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path


def create_backup(database: Path, destination_directory: Path) -> Path:
    database = database.resolve(strict=True)
    destination_directory = destination_directory.resolve()
    destination_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = destination_directory / f"taste-yourself-{timestamp}.db"

    with sqlite3.connect(database) as source, sqlite3.connect(destination) as target:
        source.backup(target)
        integrity = target.execute("PRAGMA integrity_check").fetchone()
    if not integrity or integrity[0] != "ok":
        destination.unlink(missing_ok=True)
        raise RuntimeError("Backup integrity check failed")
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a consistent online SQLite backup.")
    parser.add_argument("database", type=Path)
    parser.add_argument("destination_directory", type=Path)
    args = parser.parse_args()

    destination = create_backup(args.database, args.destination_directory)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
