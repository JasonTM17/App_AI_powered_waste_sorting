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
    select,
    text,
)
from sqlalchemy.engine import Engine

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
    Column("uart_command", String),
    Column("ack_status", String),
    Column("rtt_ms", Integer),
)


class HistoryRow:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


class HistoryService:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._engine: Engine = create_engine(f"sqlite:///{db_path}", future=True)
        metadata.create_all(self._engine)
        with self._engine.begin() as conn:
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
        uart_command=None,
        ack_status="pending",
        rtt_ms=None,
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
                    uart_command=uart_command,
                    ack_status=ack_status,
                    rtt_ms=rtt_ms,
                )
            )
            return int(res.inserted_primary_key[0])

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

    def query(self, limit=200, offset=0, cls_name=None, since: datetime | None = None):
        stmt = select(detections).order_by(detections.c.id.desc()).limit(limit).offset(offset)
        if cls_name:
            stmt = stmt.where(detections.c.cls_name == cls_name)
        if since:
            stmt = stmt.where(detections.c.ts >= since.isoformat())
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [HistoryRow(**dict(r)) for r in rows]

    def count_by_class(self) -> dict[str, int]:
        stmt = select(detections.c.cls_name, func.count()).group_by(detections.c.cls_name)
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
            "uart_command",
            "ack_status",
            "rtt_ms",
        ]
        with out_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([getattr(r, c, "") for c in cols])
        return len(rows)

    def close(self) -> None:
        self._engine.dispose()
