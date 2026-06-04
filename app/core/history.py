"""SQLite-backed detection history service via SQLAlchemy."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from sqlalchemy import (
    Column,
    Float,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.engine import Engine

from app.core.waste_categories import (
    category_for_bin_index,
    category_for_class,
    category_for_command,
    category_for_known_class,
)

metadata = MetaData()

detections = Table(
    "detections",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("track_id", Integer, nullable=False),
    Column("ts", String, nullable=False),
    Column("cls_id", Integer, nullable=False),
    Column("cls_name", String, nullable=False),
    Column("conf", Float, nullable=False),
    Column("bbox_x1", Integer),
    Column("bbox_y1", Integer),
    Column("bbox_x2", Integer),
    Column("bbox_y2", Integer),
    Column("thumbnail", LargeBinary),
    Column("image_path", String),
    Column("annotated_path", String),
    Column("meta_path", String),
    Column("route_label", String),
    Column("bin_index", Integer),
    Column("uart_command", String),
    Column("ack_status", String),
    Column("rtt_ms", Integer),
    Column("owner_account_id", Integer),
    Column("owner_username", String),
    Column("device_id", String),
)

_OPTIONAL_DETECTION_COLUMNS = {
    "image_path": "image_path TEXT",
    "annotated_path": "annotated_path TEXT",
    "meta_path": "meta_path TEXT",
    "route_label": "route_label TEXT",
    "bin_index": "bin_index INTEGER",
    "uart_command": "uart_command TEXT",
    "ack_status": "ack_status TEXT",
    "rtt_ms": "rtt_ms INTEGER",
    "owner_account_id": "owner_account_id INTEGER",
    "owner_username": "owner_username TEXT",
    "device_id": "device_id TEXT",
}


class HistoryRow:
    route_label: str | None
    bin_index: int | None
    uart_command: str | None

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _with_route_defaults(row: HistoryRow) -> HistoryRow:
    route_label = getattr(row, "route_label", None)
    bin_index = getattr(row, "bin_index", None)
    command = str(getattr(row, "uart_command", "") or "")
    cls_name = str(getattr(row, "cls_name", "") or "")
    command_category = category_for_command(command)
    class_category = category_for_known_class(cls_name)
    category = (
        command_category
        or class_category
        or category_for_bin_index(bin_index)
        or category_for_class(cls_name)
    )
    if command_category is None:
        row.uart_command = category.code
    if not route_label or command_category is None:
        row.route_label = category.name
    if bin_index is None or command_category is None:
        row.bin_index = category.bin_index
    return row


class HistoryService:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine: Engine = create_engine(f"sqlite:///{db_path}", future=True)
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
            existing_cols = {
                str(row[1]) for row in conn.execute(text("PRAGMA table_info(detections)")).all()
            }
            for name, ddl in _OPTIONAL_DETECTION_COLUMNS.items():
                if name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE detections ADD COLUMN {ddl}"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_detections_ts ON detections(ts)"))
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_detections_cls ON detections(cls_name)")
            )

    def insert(
        self,
        *,
        track_id,
        ts: datetime,
        cls_id,
        cls_name,
        conf,
        bbox,
        thumbnail=b"",
        image_path=None,
        annotated_path=None,
        meta_path=None,
        route_label=None,
        bin_index=None,
        uart_command=None,
        ack_status="pending",
        rtt_ms=None,
        owner_account_id=None,
        owner_username=None,
        device_id=None,
    ) -> int:
        x1, y1, x2, y2 = bbox
        with self._engine.begin() as conn:
            res = conn.execute(
                detections.insert().values(
                    track_id=track_id,
                    ts=ts.isoformat(),
                    cls_id=cls_id,
                    cls_name=cls_name,
                    conf=conf,
                    bbox_x1=x1,
                    bbox_y1=y1,
                    bbox_x2=x2,
                    bbox_y2=y2,
                    thumbnail=thumbnail,
                    image_path=image_path,
                    annotated_path=annotated_path,
                    meta_path=meta_path,
                    route_label=route_label,
                    bin_index=bin_index,
                    uart_command=uart_command,
                    ack_status=ack_status,
                    rtt_ms=rtt_ms,
                    owner_account_id=owner_account_id,
                    owner_username=owner_username,
                    device_id=device_id,
                )
            )
            pk = res.inserted_primary_key
            if not pk:
                raise RuntimeError("history insert did not return a primary key")
            return int(pk[0])

    def get(self, row_id: int, owner_account_id: int | None = None, owner_username: str | None = None):
        stmt = select(detections).where(detections.c.id == row_id)
        stmt = _owned_stmt(stmt, owner_account_id, owner_username)
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        return _with_route_defaults(HistoryRow(**dict(row))) if row is not None else None

    def update_ack(self, row_id: int, status: str, rtt_ms) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                detections.update()
                .where(detections.c.id == row_id)
                .values(
                    ack_status=status,
                    rtt_ms=rtt_ms,
                )
            )

    def query(
        self,
        limit=200,
        offset=0,
        cls_name=None,
        since: datetime | None = None,
        until: datetime | None = None,
        ack_status: str | None = None,
        owner_account_id: int | None = None,
        owner_username: str | None = None,
    ):
        stmt = select(detections).order_by(detections.c.id.desc()).limit(limit).offset(offset)
        if cls_name:
            stmt = stmt.where(detections.c.cls_name == cls_name)
        if since:
            stmt = stmt.where(detections.c.ts >= since.isoformat())
        if until:
            stmt = stmt.where(detections.c.ts <= until.isoformat())
        if ack_status:
            stmt = stmt.where(detections.c.ack_status == ack_status)
        stmt = _owned_stmt(stmt, owner_account_id, owner_username)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_with_route_defaults(HistoryRow(**dict(r))) for r in rows]

    def backfill_owner(
        self,
        *,
        owner_account_id: int | None,
        owner_username: str,
        device_id: str,
    ) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(
                detections.update()
                .where(or_(detections.c.owner_username.is_(None), detections.c.owner_username == ""))
                .values(
                    owner_account_id=owner_account_id,
                    owner_username=owner_username,
                    device_id=device_id,
                )
            )
            return int(result.rowcount or 0)

    def count_by_class(
        self,
        since: datetime | None = None,
        until: datetime | None = None,
        ack_status: str | None = None,
    ) -> dict[str, int]:
        stmt = select(detections.c.cls_name, func.count()).group_by(detections.c.cls_name)
        if since:
            stmt = stmt.where(detections.c.ts >= since.isoformat())
        if until:
            stmt = stmt.where(detections.c.ts <= until.isoformat())
        if ack_status:
            stmt = stmt.where(detections.c.ack_status == ack_status)
        with self._engine.begin() as conn:
            return {name: int(cnt) for name, cnt in conn.execute(stmt).all()}

    def count_by_hour(self, date: datetime) -> dict[int, int]:
        prefix = date.strftime("%Y-%m-%d")
        stmt = select(detections.c.ts).where(detections.c.ts.like(f"{prefix}%"))
        out: dict[int, int] = {h: 0 for h in range(24)}
        with self._engine.begin() as conn:
            for (ts,) in conn.execute(stmt).all():
                try:
                    hour = int(ts[11:13])
                    out[hour] = out.get(hour, 0) + 1
                except (ValueError, IndexError):
                    continue
        return out

    def export_csv(self, out_path: Path) -> int:
        rows = self.query(limit=1_000_000)
        cols = [
            "id",
            "track_id",
            "ts",
            "cls_id",
            "cls_name",
            "conf",
            "bbox_x1",
            "bbox_y1",
            "bbox_x2",
            "bbox_y2",
            "image_path",
            "annotated_path",
            "meta_path",
            "route_label",
            "bin_index",
            "uart_command",
            "ack_status",
            "rtt_ms",
            "owner_account_id",
            "owner_username",
            "device_id",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([getattr(r, c, "") for c in cols])
        return len(rows)

    def close(self) -> None:
        self._engine.dispose()


def _owned_stmt(stmt, owner_account_id: int | None, owner_username: str | None):
    clean_username = (owner_username or "").strip()
    if owner_account_id is not None:
        if clean_username:
            stmt = stmt.where(
                or_(
                    detections.c.owner_account_id == owner_account_id,
                    detections.c.owner_username == clean_username,
                )
            )
        else:
            stmt = stmt.where(detections.c.owner_account_id == owner_account_id)
    elif clean_username:
        stmt = stmt.where(detections.c.owner_username == clean_username)
    return stmt
