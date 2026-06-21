"""SQLite catalog for dataset queue images."""

from __future__ import annotations

import json
import threading
from datetime import datetime
from heapq import nlargest
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
    event,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import OperationalError

from app.core.waste_categories import canonical_class_name

metadata = MetaData()
DATASET_SQLITE_TIMEOUT_SECONDS = 30.0
DATASET_SQLITE_BUSY_TIMEOUT_MS = int(DATASET_SQLITE_TIMEOUT_SECONDS * 1000)
_SCHEMA_LOCK = threading.RLock()
_SCHEMA_READY_PATHS: set[Path] = set()
_WRITE_LOCKS_GUARD = threading.Lock()
_WRITE_LOCKS: dict[Path, threading.RLock] = {}

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
    Column("trust_state", String),
    Column("operator_label", String),
    Column("capture_session_id", String),
    Column("quality_bucket", String),
    Column("review_priority", String),
    Column("hazardous", Integer, nullable=False, default=0),
    Column("holdout", Integer, nullable=False, default=0),
    Column("recognition_enabled", Integer, nullable=False, default=0),
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

review_capture_signatures = Table(
    "review_capture_signatures",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("object_signature", String, nullable=False),
    Column("reason", String, nullable=False),
    Column("frame_fingerprint", String, nullable=False),
    Column("session_id", String, nullable=False),
    Column("item_id", String, nullable=False),
    Column("captured_at_epoch", Float, nullable=False),
)


class DatasetCatalog:
    """Small SQLite index for files in dataset_v2/low_conf_queue."""

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine: Engine = create_engine(
            f"sqlite:///{self._db_path}",
            future=True,
            connect_args={
                "timeout": DATASET_SQLITE_TIMEOUT_SECONDS,
                "check_same_thread": False,
            },
        )
        self._write_lock = _write_lock_for(self._db_path.resolve())
        self._install_sqlite_pragmas()
        self._ensure_schema_ready()

    def upsert_item(self, image_path: Path, meta: dict[str, Any]) -> None:
        values = self._values_for_item(image_path, meta)
        with self._write_lock, self._engine.begin() as conn:
            self._upsert_values(conn, values, meta)

    def index_queue(self, queue_dir: Path) -> int:
        if not queue_dir.exists():
            return 0
        indexed = 0
        seen_item_ids: list[str] = []
        prepared: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for image_path in sorted(queue_dir.glob("*.jpg")):
            meta = self._read_meta(image_path)
            if meta is None:
                continue
            values = self._values_for_item(image_path, meta)
            prepared.append((values, meta))
            seen_item_ids.append(values["item_id"])
            indexed += 1
        with self._write_lock, self._engine.begin() as conn:
            for values, meta in prepared:
                self._upsert_values(conn, values, meta)
            self._delete_missing_queue_items(conn, seen_item_ids)
        return indexed

    def index_queue_incremental(self, queue_dir: Path, *, limit: int = 1000) -> int:
        """Index only the newest queue items without deleting older catalog rows."""
        if not queue_dir.exists() or limit <= 0:
            return 0
        image_paths = nlargest(limit, queue_dir.glob("*.jpg"), key=_safe_mtime_ns)
        prepared: list[tuple[dict[str, Any], dict[str, Any]]] = []
        for image_path in image_paths:
            meta = self._read_meta(image_path)
            if meta is None:
                continue
            prepared.append((self._values_for_item(image_path, meta), meta))
        with self._write_lock, self._engine.begin() as conn:
            for values, meta in prepared:
                self._upsert_values(conn, values, meta)
        return len(prepared)

    def delete_by_image_paths(self, image_paths: list[Path]) -> None:
        item_ids = [p.stem for p in image_paths]
        if not item_ids:
            return
        with self._write_lock, self._engine.begin() as conn:
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
        trust_state: str | None = None,
        search: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = []
        if source:
            conditions.append(dataset_items.c.source == source)
        if cls_name:
            matching_names = self._matching_box_class_names(cls_name)
            conditions.append(
                select(dataset_boxes.c.id)
                .where(
                    dataset_boxes.c.item_id == dataset_items.c.item_id,
                    dataset_boxes.c.cls_name.in_(matching_names),
                )
                .exists()
            )
        if trusted is True:
            conditions.append(dataset_items.c.trusted == 1)
        elif trusted is False:
            conditions.append(dataset_items.c.trusted == 0)
        if trust_state:
            conditions.append(dataset_items.c.trust_state == trust_state)
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

    def specialist_label_stats(self, operator_label: str) -> dict[str, int]:
        """Return reviewed capture counts used by the specialist promotion gate."""
        label = str(operator_label or "").strip()
        if not label:
            return {"train": 0, "holdout": 0, "sessions": 0, "total": 0}
        condition = (
            (dataset_items.c.operator_label == label)
            & (dataset_items.c.reviewed == 1)
            & ((dataset_items.c.trusted == 1) | (dataset_items.c.holdout == 1))
        )
        with self._engine.begin() as conn:
            total = int(
                conn.execute(
                    select(func.count()).select_from(dataset_items).where(condition)
                ).scalar_one()
            )
            holdout = int(
                conn.execute(
                    select(func.count())
                    .select_from(dataset_items)
                    .where(condition, dataset_items.c.holdout == 1)
                ).scalar_one()
            )
            sessions = int(
                conn.execute(
                    select(func.count(func.distinct(dataset_items.c.capture_session_id))).where(
                        condition,
                        dataset_items.c.capture_session_id.is_not(None),
                    )
                ).scalar_one()
            )
        return {
            "train": max(0, total - holdout),
            "holdout": holdout,
            "sessions": sessions,
            "total": total,
        }

    def list_items_for_box_class(
        self,
        cls_name: str,
        *,
        limit: int | None = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """List distinct items containing the class in any annotation box."""
        class_filter = dataset_boxes.c.cls_name.in_(self._matching_box_class_names(cls_name))
        total_stmt = (
            select(func.count(func.distinct(dataset_items.c.item_id)))
            .select_from(dataset_items.join(dataset_boxes, dataset_boxes.c.item_id == dataset_items.c.item_id))
            .where(class_filter)
        )
        rows_stmt = (
            select(dataset_items)
            .join(dataset_boxes, dataset_boxes.c.item_id == dataset_items.c.item_id)
            .where(class_filter)
            .distinct()
            .order_by(dataset_items.c.updated_at.desc(), dataset_items.c.id.desc())
            .offset(offset)
        )
        if limit is not None:
            rows_stmt = rows_stmt.limit(limit)
        with self._engine.begin() as conn:
            total = int(conn.execute(total_stmt).scalar_one())
            rows = [dict(row._mapping) for row in conn.execute(rows_stmt).all()]
        return rows, total

    def count_trust_states_for_box_class(self, cls_name: str) -> dict[str, int]:
        """Count distinct class items by their current review/trust state."""
        stmt = (
            select(dataset_items.c.trust_state, func.count(func.distinct(dataset_items.c.item_id)))
            .select_from(dataset_items.join(dataset_boxes, dataset_boxes.c.item_id == dataset_items.c.item_id))
            .where(dataset_boxes.c.cls_name.in_(self._matching_box_class_names(cls_name)))
            .group_by(dataset_items.c.trust_state)
        )
        with self._engine.begin() as conn:
            return {
                str(state): int(count)
                for state, count in conn.execute(stmt).all()
                if state is not None
            }

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

    def count_by_trust_state(self) -> dict[str, int]:
        stmt = select(dataset_items.c.trust_state, func.count()).group_by(dataset_items.c.trust_state)
        with self._engine.begin() as conn:
            return {
                str(state): int(count)
                for state, count in conn.execute(stmt).all()
                if state is not None
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

    def has_recent_review_capture(
        self,
        *,
        object_signature: str,
        reason: str,
        frame_fingerprint: str,
        now_epoch: float,
        cooldown_seconds: float,
        similar_scene_seconds: float,
        max_hamming_distance: int = 72,
    ) -> bool:
        stmt = (
            select(
                review_capture_signatures.c.frame_fingerprint,
                review_capture_signatures.c.captured_at_epoch,
            )
            .where(
                review_capture_signatures.c.object_signature == object_signature,
                review_capture_signatures.c.reason == reason,
                review_capture_signatures.c.captured_at_epoch
                >= float(now_epoch) - max(float(cooldown_seconds), float(similar_scene_seconds)),
            )
            .order_by(review_capture_signatures.c.captured_at_epoch.desc())
            .limit(8)
        )
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).all()
        for previous_fingerprint, captured_at in rows:
            age = float(now_epoch) - float(captured_at)
            if age < float(cooldown_seconds):
                return True
            if age <= float(similar_scene_seconds) and _hex_hamming_distance(
                str(frame_fingerprint),
                str(previous_fingerprint),
            ) <= int(max_hamming_distance):
                return True
        return False

    def record_review_capture(
        self,
        *,
        object_signature: str,
        reason: str,
        frame_fingerprint: str,
        session_id: str,
        item_id: str,
        captured_at_epoch: float,
    ) -> None:
        values = {
            "object_signature": object_signature,
            "reason": reason,
            "frame_fingerprint": frame_fingerprint,
            "session_id": session_id,
            "item_id": item_id,
            "captured_at_epoch": float(captured_at_epoch),
        }
        with self._write_lock, self._engine.begin() as conn:
            conn.execute(review_capture_signatures.insert().values(**values))
            cutoff = float(captured_at_epoch) - 86400.0
            conn.execute(
                review_capture_signatures.delete().where(
                    review_capture_signatures.c.captured_at_epoch < cutoff
                )
            )

    def _matching_box_class_names(self, cls_name: str) -> list[str]:
        requested = canonical_class_name(cls_name) or str(cls_name).strip()
        stmt = select(dataset_boxes.c.cls_name).distinct()
        with self._engine.begin() as conn:
            names = [str(name) for (name,) in conn.execute(stmt).all() if name]
        matches = [name for name in names if canonical_class_name(name) == requested]
        return matches or [str(cls_name).strip()]

    def close(self) -> None:
        self._engine.dispose()

    def _ensure_schema_ready(self) -> None:
        path_key = self._db_path.resolve()
        if path_key in _SCHEMA_READY_PATHS and self._db_path.exists():
            return
        with _SCHEMA_LOCK:
            if path_key in _SCHEMA_READY_PATHS and self._db_path.exists():
                return
            try:
                self._create_schema()
            except OperationalError as exc:
                if is_sqlite_database_locked(exc):
                    self._engine.dispose()
                raise
            _SCHEMA_READY_PATHS.add(path_key)

    def _create_schema(self) -> None:
        with self._write_lock:
            if self._engine.dialect.name == "sqlite":
                with self._engine.connect() as conn:
                    conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            metadata.create_all(self._engine)
        with self._write_lock, self._engine.begin() as conn:
            self._configure_sqlite_connection(conn)
            self._ensure_columns(conn)
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_source ON dataset_items(source)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_cls ON dataset_items(cls_name)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_trusted ON dataset_items(trusted)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_trust_state ON dataset_items(trust_state)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_reviewed ON dataset_items(reviewed)"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_dataset_operator_label "
                    "ON dataset_items(operator_label, reviewed, holdout)"
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_boxes_item ON dataset_boxes(item_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dataset_boxes_cls ON dataset_boxes(cls_name)"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_review_capture_signature "
                    "ON review_capture_signatures(object_signature, reason, captured_at_epoch)"
                )
            )

    @staticmethod
    def _configure_sqlite_connection(conn: Connection) -> None:
        if conn.dialect.name != "sqlite":
            return
        conn.execute(text(f"PRAGMA busy_timeout={DATASET_SQLITE_BUSY_TIMEOUT_MS}"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))

    def _install_sqlite_pragmas(self) -> None:
        @event.listens_for(self._engine, "connect")
        def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            try:
                cursor.execute(f"PRAGMA busy_timeout={DATASET_SQLITE_BUSY_TIMEOUT_MS}")
                cursor.execute("PRAGMA synchronous=NORMAL")
            finally:
                cursor.close()

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
            "trust_state": _meta_trust_state(meta),
            "operator_label": str(meta.get("operator_label") or "").strip() or None,
            "capture_session_id": str(meta.get("capture_session_id") or "").strip() or None,
            "quality_bucket": str(meta.get("quality_bucket") or "").strip() or None,
            "review_priority": str(meta.get("review_priority") or "").strip() or None,
            "hazardous": 1 if bool(meta.get("hazardous")) else 0,
            "holdout": 1 if bool(meta.get("holdout")) or meta.get("split") == "holdout" else 0,
            "recognition_enabled": 1 if bool(meta.get("recognition_enabled")) else 0,
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
        if "trust_state" not in existing:
            conn.execute(text("ALTER TABLE dataset_items ADD COLUMN trust_state VARCHAR(255)"))
        additions = {
            "operator_label": "VARCHAR(255)",
            "capture_session_id": "VARCHAR(255)",
            "quality_bucket": "VARCHAR(255)",
            "review_priority": "VARCHAR(255)",
            "hazardous": "INTEGER NOT NULL DEFAULT 0",
            "holdout": "INTEGER NOT NULL DEFAULT 0",
            "recognition_enabled": "INTEGER NOT NULL DEFAULT 0",
        }
        for column_name, column_type in additions.items():
            if column_name not in existing:
                conn.execute(
                    text(f"ALTER TABLE dataset_items ADD COLUMN {column_name} {column_type}")
                )


def _safe_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[i : i + size] for i in range(0, len(values), size)]


def _hex_hamming_distance(first: str, second: str) -> int:
    try:
        first_bytes = bytes.fromhex(first)
        second_bytes = bytes.fromhex(second)
    except ValueError:
        return 10_000
    if len(first_bytes) != len(second_bytes):
        return 10_000
    return sum(
        (left ^ right).bit_count()
        for left, right in zip(first_bytes, second_bytes, strict=True)
    )


def is_sqlite_database_locked(exc: BaseException) -> bool:
    return "database is locked" in str(exc).casefold()


def _write_lock_for(path: Path) -> threading.RLock:
    with _WRITE_LOCKS_GUARD:
        lock = _WRITE_LOCKS.get(path)
        if lock is None:
            lock = threading.RLock()
            _WRITE_LOCKS[path] = lock
        return lock


def _meta_reviewed(meta: dict[str, Any]) -> bool:
    return bool(meta.get("reviewed"))


def _meta_trusted(meta: dict[str, Any]) -> bool:
    from app.core.dataset_trust import classify_dataset_item

    return classify_dataset_item(meta).trainable


def _meta_trust_state(meta: dict[str, Any]) -> str:
    from app.core.dataset_trust import classify_dataset_item

    return classify_dataset_item(meta).state.value


__all__ = ["DatasetCatalog", "dataset_boxes", "dataset_items", "is_sqlite_database_locked"]
