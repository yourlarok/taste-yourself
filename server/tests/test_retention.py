import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.repositories.experience import ExperienceRepository
from app.repositories.wardrobe import WardrobeRepository
from app.services.retention import RetentionService


def test_retention_purges_expired_person_and_result_media(tmp_path: Path):
    database = tmp_path / "retention.db"
    media_root = tmp_path / "media"
    WardrobeRepository(database)
    ExperienceRepository(database)
    person_file = media_root / "people" / "old.jpg"
    result_file = media_root / "results" / "old.jpg"
    person_file.parent.mkdir(parents=True)
    result_file.parent.mkdir(parents=True)
    person_file.write_bytes(b"person")
    result_file.write_bytes(b"result")
    old = (datetime.now(UTC) - timedelta(days=40)).isoformat()

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO person_images (id, user_id, image_path, width, height, created_at)
            VALUES ('person-1', 'user-1', 'people/old.jpg', 320, 480, ?)
            """,
            (old,),
        )
        connection.execute(
            """
            INSERT INTO tryon_results (id, experience_session_id, result_path, created_at)
            VALUES ('result-1', 'session-1', 'results/old.jpg', ?)
            """,
            (old,),
        )

    counts = RetentionService(database, media_root).purge(person_days=7, result_days=30)

    assert counts == {"person_images": 1, "tryon_results": 1, "media_files": 2}
    assert not person_file.exists()
    assert not result_file.exists()
