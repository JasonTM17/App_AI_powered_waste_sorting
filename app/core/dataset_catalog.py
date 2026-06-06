"""SQLite catalog for dataset queue images."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine

metadata = MetaData()

dataset_items = Table(
    "dataset_items",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("item_id", String, nullable=False, unique=True),
    Column("image_path", String, nullable=False),
    Column("meta_path", String, nullable=False),
    Column("source", String, nullable=False),
    Column("cls_id", Integer),
    Column("cls_name", String),
    Column("box_count", Integer, nullable=False, default=0),
    Column("width", Integer),
    Column("height", Integer),
    Column("split", String),
    Column("original_file", String),
    Column("ts", String),
    Column("reviewed", Integer, nullable=False, default=0),
    Column("trusted", Integer, nullable=False, default=1),
    Column("updated_at", String, nullable=False),
)

dataset_boxes = Table(
    "dataset_boxes",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("item_id", String, nullable=False),
    Column("box_index", Integer, nullable=False),
    Column("cls_id", Integer),
    Column("cls_name", String),
    Column("conf", Float),
    Column("x1", Float),
    Column("y1", Float),
    Column("x2", Float),
    Column("y2", Float),
    Column("updated_at", String, nullable=False),
)


class DatasetCatalog:
    """Small SQLite index for files in dataset_v2/low_conf_queue."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine: Engine = create_engine(f"sqlite:///{db_path}", future=True)
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            self._ensure_columns(conn)
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_source ON dataset_items(source)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_cls ON dataset_items(cls_name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_trusted ON dataset_items(trusted)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_reviewed ON dataset_items(reviewed)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_boxes_item ON dataset_boxes(item_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_boxes_cls ON dataset_boxes(cls_name)"))

    def upsert_item(self, image_path: Path, meta: dict[str, Any]) -> None:
        values = self._values_for_item(image_path, meta)
        with self._engine.begin() as conn:
            self._upsert_values(conn, values, meta)

    def index_queue(self, queue_dir: Path) -> int:
        if not queue_dir.exists():
            return 0
        indexed = 0
        seen_item_ids: list[str] = []
        with self._engine.begin() as conn:
            for image_path in sorted(queue_dir.glob("*.jpg")):
                meta = self._read_meta(image_path)
                if meta is None:
                    continue
                values = self._values_for_item(image_path, meta)
                self._upsert_values(conn, values, meta)
                seen_item_ids.append(values["item_id"])
                indexed += 1
            self._delete_missing_queue_items(conn, seen_item_ids)
        return indexed

    def delete_by_image_paths(self, image_paths: list[Path]) -> None:
        item_ids = [p.stem for p in image_paths]
        if not item_ids:
            return
        with self._engine.begin() as conn:
            conn.execute(dataset_boxes.delete().where(dataset_boxes.c.item_id.in_(item_ids)))
            conn.execute(dataset_items.delete().where(dataset_items.c.item_id.in_(item_ids)))

    def list_items(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        source: str | None = None,
        cls_name: str | None = None,
        trusted: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = []
        if source:
            conditions.append(dataset_items.c.source == source)
        if cls_name:
            conditions.append(dataset_items.c.cls_name == cls_name)
        if trusted is True:
            conditions.append(dataset_items.c.trusted == 1)
        elif trusted is False:
            conditions.append(dataset_items.c.trusted == 0)
        if search:
            pattern = f"%{search}%"
            conditions.append(
                or_(
                    dataset_items.c.item_id.like(pattern),
                    dataset_items.c.source.like(pattern),
                    dataset_items.c.cls_name.like(pattern),
                    dataset_items.c.image_path.like(pattern),
                    dataset_items.c.original_file.like(pattern),
                )
            )

        total_stmt = select(func.count()).select_from(dataset_items)
        rows_stmt = (
            select(dataset_items)
            .order_by(dataset_items.c.updated_at.desc(), dataset_items.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        for condition in conditions:
            total_stmt = total_stmt.where(condition)
            rows_stmt = rows_stmt.where(condition)

        with self._engine.begin() as conn:
            total = int(conn.execute(total_stmt).scalar_one())
            rows = [dict(row._mapping) for row in conn.execute(rows_stmt).all()]
        return rows, total

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        stmt = select(dataset_items).where(dataset_items.c.item_id == item_id)
        with self._engine.begin() as conn:
            row = conn.execute(stmt).first()
        return dict(row._mapping) if row is not None else None

    def list_boxes(self, item_id: str) -> list[dict[str, Any]]:
        stmt = (
            select(dataset_boxes)
            .where(dataset_boxes.c.item_id == item_id)
            .order_by(dataset_boxes.c.box_index.asc())
        )
        with self._engine.begin() as conn:
            return [dict(row._mapping) for row in conn.execute(stmt).all()]

    def count_total(self) -> int:
        stmt = select(func.count()).select_from(dataset_items)
        with self._engine.begin() as conn:
            return int(conn.execute(stmt).scalar_one())

    def count_by_source(self) -> dict[str, int]:
        stmt = select(dataset_items.c.source, func.count()).group_by(dataset_items.c.source)
        with self._engine.begin() as conn:
            return {source: int(count) for source, count in conn.execute(stmt).all()}

    def count_by_trusted(self) -> dict[str, int]:
        stmt = select(dataset_items.c.trusted, func.count()).group_by(dataset_items.c.trusted)
        with self._engine.begin() as conn:
            raw = {int(trusted): int(count) for trusted, count in conn.execute(stmt).all()}
        return {
            "trainable": raw.get(1, 0),
            "needs_review": raw.get(0, 0),
        }

    def count_boxes_total(self) -> int:
        stmt = select(func.count()).select_from(dataset_boxes)
        with self._engine.begin() as conn:
            return int(conn.execute(stmt).scalar_one())

    def count_box_classes(self) -> dict[str, int]:
        stmt = select(dataset_boxes.c.cls_name, func.count()).group_by(dataset_boxes.c.cls_name)
        with self._engine.begin() as conn:
            return {
                str(name): int(count)
                for name, count in conn.execute(stmt).all()
                if name is not None
            }

    def count_distinct_box_classes(self) -> int:
        stmt = select(func.count(func.distinct(dataset_boxes.c.cls_name)))
        with self._engine.begin() as conn:
            return int(conn.execute(stmt).scalar_one())

    def close(self) -> None:
        self._engine.dispose()

    def _upsert_values(self, conn: Connection, values: dict[str, Any], meta: dict[str, Any]) -> None:
        existing = conn.execute(
            select(dataset_items.c.id).where(dataset_items.c.item_id == values["item_id"])
        ).scalar_one_or_none()
        if existing is None:
            conn.execute(dataset_items.insert().values(**values))
        else:
            conn.execute(
                dataset_items.update()
                .where(dataset_items.c.id == existing)
                .values(**values)
            )
        self._replace_box_values(conn, values["item_id"], meta)

    def _replace_box_values(self, conn: Connection, item_id: str, meta: dict[str, Any]) -> None:
        conn.execute(dataset_boxes.delete().where(dataset_boxes.c.item_id == item_id))
        rows = self._values_for_boxes(item_id, meta)
        if rows:
            conn.execute(dataset_boxes.insert(), rows)

    def _delete_missing_queue_items(self, conn: Connection, seen_item_ids: list[str]) -> None:
        if not seen_item_ids:
            conn.execute(dataset_boxes.delete())
            conn.execute(dataset_items.delete())
            return
        seen = set(seen_item_ids)
        existing = {
            str(item_id)
            for (item_id,) in conn.execute(select(dataset_items.c.item_id)).all()
        }
        stale = sorted(existing - seen)
        for chunk in _chunks(stale, 500):
            conn.execute(dataset_boxes.delete().where(dataset_boxes.c.item_id.in_(chunk)))
            conn.execute(dataset_items.delete().where(dataset_items.c.item_id.in_(chunk)))

    def _values_for_item(self, image_path: Path, meta: dict[str, Any]) -> dict[str, Any]:
        width, height = self._image_size(image_path)
        boxes = meta.get("boxes") or []
        first_box = boxes[0] if boxes else {}
        return {
            "item_id": image_path.stem,
            "image_path": str(image_path.resolve()),
            "meta_path": str(image_path.with_suffix(".json").resolve()),
            "source": str(meta.get("source") or "unknown"),
            "cls_id": self._optional_int(first_box.get("cls_id")),
            "cls_name": first_box.get("cls_name"),
            "box_count": len(boxes),
            "width": width,
            "height": height,
            "split": meta.get("split"),
            "original_file": meta.get("original_file"),
            "ts": meta.get("ts"),
            "reviewed": 1 if _meta_reviewed(meta) else 0,
            "trusted": 1 if _meta_trusted(meta) else 0,
            "updated_at": datetime.now().isoformat(),
        }

    def _values_for_boxes(self, item_id: str, meta: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        updated_at = datetime.now().isoformat()
        for idx, box in enumerate(meta.get("boxes") or []):
            xyxy = box.get("xyxy") or [None, None, None, None]
            rows.append(
                {
                    "item_id": item_id,
                    "box_index": idx,
                    "cls_id": self._optional_int(box.get("cls_id")),
                    "cls_name": box.get("cls_name"),
                    "conf": self._optional_float(box.get("conf")),
                    "x1": self._optional_float(xyxy[0] if len(xyxy) > 0 else None),
                    "y1": self._optional_float(xyxy[1] if len(xyxy) > 1 else None),
                    "x2": self._optional_float(xyxy[2] if len(xyxy) > 2 else None),
                    "y2": self._optional_float(xyxy[3] if len(xyxy) > 3 else None),
                    "updated_at": updated_at,
                }
            )
        return rows

    @staticmethod
    def _read_meta(image_path: Path) -> dict[str, Any] | None:
        meta_path = image_path.with_suffix(".json")
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return cast(dict[str, Any], data) if isinstance(data, dict) else None

    @staticmethod
    def _image_size(image_path: Path) -> tuple[int | None, int | None]:
        try:
            from PIL import Image

            with Image.open(image_path) as image:
                width, height = image.size
                return int(width), int(height)
        except Exception:
            return None, None

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if value is None:
            return None
        if not isinstance(value, str | bytes | bytearray | int | float):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _optional_float(value: object) -> float | None:
        if value is None:
            return None
        if not isinstance(value, str | bytes | bytearray | int | float):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ensure_columns(conn: Connection) -> None:
        rows = conn.execute(text("PRAGMA table_info(dataset_items)")).all()
        existing = {str(row[1]) for row in rows}
        if "reviewed" not in existing:
            conn.execute(text("ALTER TABLE dataset_items ADD COLUMN reviewed INTEGER NOT NULL DEFAULT 0"))
        if "trusted" not in existing:
            conn.execute(text("ALTER TABLE dataset_items ADD COLUMN trusted INTEGER NOT NULL DEFAULT 1"))


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _meta_reviewed(meta: dict[str, Any]) -> bool:
    return bool(meta.get("reviewed"))


def _meta_trusted(meta: dict[str, Any]) -> bool:
    source = str(meta.get("source") or "unknown")
    if source in {"unknown", "untrusted"}:
        return False
    if source == "auto_low_conf" and not _meta_reviewed(meta):
        return False
    return not meta.get("unknown_labels")


__all__ = ["DatasetCatalog", "dataset_boxes", "dataset_items"]
