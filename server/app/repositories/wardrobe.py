from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.domain.models import ProductFitData
from app.domain.wardrobe import GarmentRecord, PersonImageRecord
from app.services.image_storage import StoredImage


class WardrobeRepository:
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
                CREATE TABLE IF NOT EXISTS wardrobe_garments (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  category TEXT NOT NULL,
                  image_path TEXT NOT NULL,
                  status TEXT NOT NULL,
                  width INTEGER NOT NULL,
                  height INTEGER NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_wardrobe_user
                  ON wardrobe_garments (user_id, created_at);

                CREATE TABLE IF NOT EXISTS person_images (
                  id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  image_path TEXT NOT NULL,
                  width INTEGER NOT NULL,
                  height INTEGER NOT NULL,
                  created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_person_user
                  ON person_images (user_id, created_at);

                CREATE TABLE IF NOT EXISTS garment_size_charts (
                  garment_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  product_json TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_size_chart_user
                  ON garment_size_charts (user_id, updated_at);
                """
            )
            existing = {
                row["name"] for row in connection.execute("PRAGMA table_info(wardrobe_garments)")
            }
            migrations = {
                "source_type": "TEXT NOT NULL DEFAULT 'upload'",
                "source_url": "TEXT",
                "external_item_id": "TEXT",
                "brand": "TEXT",
                "audience": "TEXT NOT NULL DEFAULT 'unknown'",
                "body_types_json": "TEXT NOT NULL DEFAULT '[]'",
                "occasions_json": "TEXT NOT NULL DEFAULT '[]'",
                "tags_json": "TEXT NOT NULL DEFAULT '[]'",
            }
            for name, definition in migrations.items():
                if name not in existing:
                    connection.execute(
                        f"ALTER TABLE wardrobe_garments ADD COLUMN {name} {definition}"
                    )
            connection.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_wardrobe_external
                ON wardrobe_garments (user_id, source_type, external_item_id)
                WHERE external_item_id IS NOT NULL
                """
            )

    def add_garment(
        self,
        user_id: str,
        name: str,
        category: str,
        image: StoredImage,
        *,
        source_type: str = "upload",
        source_url: str | None = None,
        external_item_id: str | None = None,
        brand: str | None = None,
        audience: str = "unknown",
        body_types: list[str] | None = None,
        occasions: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> GarmentRecord:
        record = GarmentRecord(
            id=str(uuid4()),
            user_id=user_id,
            name=name,
            category=category,
            image_path=image.relative_path,
            status="ready",
            width=image.width,
            height=image.height,
            source_type=source_type,
            source_url=source_url,
            external_item_id=external_item_id,
            brand=brand,
            audience=audience,
            body_types=body_types or [],
            occasions=occasions or [],
            tags=tags or [],
            created_at=datetime.now(UTC),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO wardrobe_garments (
                  id, user_id, name, category, image_path, status, width, height,
                  source_type, source_url, external_item_id, brand, audience,
                  body_types_json, occasions_json, tags_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.user_id,
                    record.name,
                    record.category,
                    record.image_path,
                    record.status,
                    record.width,
                    record.height,
                    record.source_type,
                    record.source_url,
                    record.external_item_id,
                    record.brand,
                    record.audience,
                    json.dumps(record.body_types, ensure_ascii=False),
                    json.dumps(record.occasions, ensure_ascii=False),
                    json.dumps(record.tags, ensure_ascii=False),
                    record.created_at.isoformat(),
                ),
            )
        return record

    def list_garments(self, user_id: str) -> list[GarmentRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM wardrobe_garments
                WHERE user_id = ? ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._row_to_garment(row) for row in rows]

    def get_garment(self, garment_id: str) -> GarmentRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM wardrobe_garments WHERE id = ?", (garment_id,)
            ).fetchone()
        return self._row_to_garment(row) if row else None

    def get_external_garment(
        self, user_id: str, source_type: str, external_item_id: str
    ) -> GarmentRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM wardrobe_garments
                WHERE user_id = ? AND source_type = ? AND external_item_id = ?
                """,
                (user_id, source_type, external_item_id),
            ).fetchone()
        return self._row_to_garment(row) if row else None

    @staticmethod
    def _row_to_garment(row: sqlite3.Row) -> GarmentRecord:
        data = dict(row)
        data["body_types"] = json.loads(data.pop("body_types_json", "[]"))
        data["occasions"] = json.loads(data.pop("occasions_json", "[]"))
        data["tags"] = json.loads(data.pop("tags_json", "[]"))
        return GarmentRecord.model_validate(data)

    def add_person_image(self, user_id: str, image: StoredImage) -> PersonImageRecord:
        record = PersonImageRecord(
            id=str(uuid4()),
            user_id=user_id,
            image_path=image.relative_path,
            width=image.width,
            height=image.height,
            created_at=datetime.now(UTC),
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO person_images (
                  id, user_id, image_path, width, height, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.user_id,
                    record.image_path,
                    record.width,
                    record.height,
                    record.created_at.isoformat(),
                ),
            )
        return record

    def get_person_image(self, image_id: str) -> PersonImageRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM person_images WHERE id = ?", (image_id,)
            ).fetchone()
        return PersonImageRecord.model_validate(dict(row)) if row else None

    def save_size_chart(
        self,
        garment_id: str,
        user_id: str,
        product: ProductFitData,
    ) -> ProductFitData:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO garment_size_charts (
                  garment_id, user_id, product_json, updated_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(garment_id) DO UPDATE SET
                  user_id = excluded.user_id,
                  product_json = excluded.product_json,
                  updated_at = excluded.updated_at
                """,
                (
                    garment_id,
                    user_id,
                    product.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return product

    def get_size_chart(self, garment_id: str, user_id: str) -> ProductFitData | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT product_json FROM garment_size_charts
                WHERE garment_id = ? AND user_id = ?
                """,
                (garment_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return ProductFitData.model_validate(json.loads(row["product_json"]))
