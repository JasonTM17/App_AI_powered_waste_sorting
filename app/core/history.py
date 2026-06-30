"""SQLite-backed detection history service via SQLAlchemy."""

from __future__ import annotations

import csv
import json
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

from app.core.history_labels import infer_history_label, validate_review_label
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
    Column("hazardous", Integer, nullable=False, default=0),
    Column("hazardous_confirmed_by", String),
    Column("hazardous_confirmed_at", String),
    Column("display_label", String),
    Column("label_status", String),
    Column("label_source", String),
    Column("label_confidence", Float),
    Column("reviewed_by", String),
    Column("reviewed_at", String),
    Column("review_note", String),
)

history_label_audit = Table(
    "history_label_audit",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("history_id", Integer, nullable=False),
    Column("previous_label", String),
    Column("new_label", String, nullable=False),
    Column("previous_status", String),
    Column("new_status", String, nullable=False),
    Column("reviewed_by", String, nullable=False),
    Column("reviewed_at", String, nullable=False),
    Column("review_note", String),
)

qa_sessions = Table(
    "qa_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("started_at", String, nullable=False),
    Column("completed_at", String),
    Column("phase", String, nullable=False),
    Column("status", String, nullable=False),
    Column("repetitions", Integer, nullable=False),
    Column("countdown_seconds", Float, nullable=False),
    Column("scan_timeout_seconds", Float, nullable=False),
    Column("model_path", String),
    Column("model_hash", String),
    Column("sample_count", Integer, nullable=False),
    Column("config_json", String),
)

qa_trials = Table(
    "qa_trials",
    metadata,
    Column("id", String, primary_key=True),
    Column("session_id", String, nullable=False),
    Column("sample_index", Integer, nullable=False),
    Column("sample_label", String, nullable=False),
    Column("expected_class", String, nullable=False),
    Column("expected_route", String, nullable=False),
    Column("trial_number", Integer, nullable=False),
    Column("phase", String, nullable=False),
    Column("started_at", String, nullable=False),
    Column("completed_at", String, nullable=False),
    Column("verdict", String, nullable=False),
    Column("predicted_class", String),
    Column("predicted_route", String),
    Column("confidence", Float),
    Column("bbox_x1", Integer),
    Column("bbox_y1", Integer),
    Column("bbox_x2", Integer),
    Column("bbox_y2", Integer),
    Column("detection_count", Integer, nullable=False),
    Column("raw_image_path", String),
    Column("annotated_image_path", String),
    Column("meta_path", String),
    Column("guard_reason", String),
    Column("speaker_mode", String),
    Column("uart_payload", String),
    Column("ack_status", String),
    Column("rtt_ms", Integer),
    Column("model_hash", String),
    Column("promoted_path", String),
    Column("extra_json", String),
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
    "hazardous": "hazardous INTEGER DEFAULT 0",
    "hazardous_confirmed_by": "hazardous_confirmed_by TEXT",
    "hazardous_confirmed_at": "hazardous_confirmed_at TEXT",
    "display_label": "display_label TEXT",
    "label_status": "label_status TEXT",
    "label_source": "label_source TEXT",
    "label_confidence": "label_confidence REAL",
    "reviewed_by": "reviewed_by TEXT",
    "reviewed_at": "reviewed_at TEXT",
    "review_note": "review_note TEXT",
}


class HistoryRow:
    route_label: str | None
    bin_index: int | None
    uart_command: str | None
    display_label: str | None
    label_status: str | None
    label_source: str | None
    label_confidence: float | None

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
    if not str(getattr(row, "display_label", "") or "").strip():
        decision = infer_history_label(
            cls_name=cls_name,
            confidence=getattr(row, "conf", None),
            meta_path=getattr(row, "meta_path", None),
            image_available=bool(
                getattr(row, "image_path", None) or getattr(row, "annotated_path", None)
            ),
        )
        row.display_label = decision.display_label
        row.label_status = decision.label_status
        row.label_source = decision.label_source
        row.label_confidence = decision.label_confidence
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
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_detections_label_status "
                    "ON detections(label_status)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_history_label_audit_history "
                    "ON history_label_audit(history_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_qa_trials_session "
                    "ON qa_trials(session_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_qa_trials_completed "
                    "ON qa_trials(completed_at)"
                )
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
        hazardous=False,
        hazardous_confirmed_by=None,
        hazardous_confirmed_at=None,
        display_label=None,
        label_status=None,
        label_source=None,
        label_confidence=None,
        reviewed_by=None,
        reviewed_at=None,
        review_note=None,
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
                    hazardous=1 if hazardous else 0,
                    hazardous_confirmed_by=hazardous_confirmed_by,
                    hazardous_confirmed_at=hazardous_confirmed_at,
                    display_label=display_label,
                    label_status=label_status,
                    label_source=label_source,
                    label_confidence=label_confidence,
                    reviewed_by=reviewed_by,
                    reviewed_at=reviewed_at,
                    review_note=review_note,
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
        label_status: str | None = None,
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
        if label_status:
            stmt = stmt.where(detections.c.label_status == label_status)
        stmt = _owned_stmt(stmt, owner_account_id, owner_username)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [_with_route_defaults(HistoryRow(**dict(r))) for r in rows]

    def backfill_labels(self) -> list[dict[str, object]]:
        """Persist deterministic labels and missing route fields; safe to run repeatedly."""
        changes: list[dict[str, object]] = []
        with self._engine.begin() as conn:
            rows = conn.execute(select(detections).order_by(detections.c.id)).mappings().all()
            for raw in rows:
                row = HistoryRow(**dict(raw))
                routed = _with_route_defaults(row)
                current_status = str(raw.get("label_status") or "")
                preserve_review = (
                    current_status in {"human_verified", "needs_review", "no_evidence"}
                    and str(raw.get("label_source") or "") == "admin_review"
                )
                if preserve_review:
                    decision_values = {
                        "display_label": raw.get("display_label"),
                        "label_status": current_status,
                        "label_source": raw.get("label_source") or "admin_review",
                        "label_confidence": raw.get("label_confidence"),
                    }
                else:
                    decision = infer_history_label(
                        cls_name=str(raw.get("cls_name") or ""),
                        confidence=raw.get("conf"),
                        meta_path=raw.get("meta_path"),
                        image_available=bool(raw.get("image_path") or raw.get("annotated_path")),
                    )
                    decision_values = {
                        "display_label": decision.display_label,
                        "label_status": decision.label_status,
                        "label_source": decision.label_source,
                        "label_confidence": decision.label_confidence,
                    }
                values = dict(decision_values)
                if not str(raw.get("route_label") or "").strip():
                    values["route_label"] = routed.route_label
                if raw.get("bin_index") is None:
                    values["bin_index"] = routed.bin_index
                if category_for_command(str(raw.get("uart_command") or "")) is None:
                    values["uart_command"] = routed.uart_command
                before = {key: raw.get(key) for key in values}
                if before == values:
                    continue
                conn.execute(
                    detections.update().where(detections.c.id == int(raw["id"])).values(**values)
                )
                changes.append(
                    {
                        "id": int(raw["id"]),
                        "cls_name": str(raw.get("cls_name") or ""),
                        "before": before,
                        "after": values,
                    }
                )
        return changes

    def review_label(
        self,
        row_id: int,
        *,
        display_label: str,
        reviewed_by: str,
        review_note: str = "",
        status: str = "human_verified",
    ) -> HistoryRow:
        if status not in {"human_verified", "no_evidence", "needs_review"}:
            raise ValueError("Trạng thái duyệt không hợp lệ.")
        label = (
            validate_review_label(display_label)
            if status == "human_verified"
            else "Chưa xác định vật"
        )
        reviewer = str(reviewed_by or "").strip()
        if not reviewer:
            raise ValueError("Thiếu tài khoản người duyệt.")
        reviewed_at = datetime.now().astimezone().isoformat()
        with self._engine.begin() as conn:
            raw = conn.execute(
                select(detections).where(detections.c.id == row_id)
            ).mappings().first()
            if raw is None:
                raise KeyError(row_id)
            conn.execute(
                history_label_audit.insert().values(
                    history_id=row_id,
                    previous_label=raw.get("display_label"),
                    new_label=label,
                    previous_status=raw.get("label_status"),
                    new_status=status,
                    reviewed_by=reviewer,
                    reviewed_at=reviewed_at,
                    review_note=str(review_note or "").strip()[:500],
                )
            )
            conn.execute(
                detections.update()
                .where(detections.c.id == row_id)
                .values(
                    display_label=label,
                    label_status=status,
                    label_source="admin_review",
                    label_confidence=1.0 if status == "human_verified" else None,
                    reviewed_by=reviewer,
                    reviewed_at=reviewed_at,
                    review_note=str(review_note or "").strip()[:500],
                )
            )
        result = self.get(row_id)
        if result is None:
            raise KeyError(row_id)
        return result

    def label_audit(self, row_id: int) -> list[HistoryRow]:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(history_label_audit)
                .where(history_label_audit.c.history_id == row_id)
                .order_by(history_label_audit.c.id.desc())
            ).mappings().all()
        return [HistoryRow(**dict(row)) for row in rows]

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
        cls_name: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        ack_status: str | None = None,
    ) -> dict[str, int]:
        stmt = select(detections.c.cls_name, func.count()).group_by(detections.c.cls_name)
        if cls_name:
            stmt = stmt.where(detections.c.cls_name == cls_name)
        if since:
            stmt = stmt.where(detections.c.ts >= since.isoformat())
        if until:
            stmt = stmt.where(detections.c.ts <= until.isoformat())
        if ack_status:
            stmt = stmt.where(detections.c.ack_status == ack_status)
        with self._engine.begin() as conn:
            return {name: int(cnt) for name, cnt in conn.execute(stmt).all()}

    def count_by_hour_range(
        self,
        *,
        cls_name: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        ack_status: str | None = None,
    ) -> dict[int, int]:
        stmt = select(detections.c.ts)
        if cls_name:
            stmt = stmt.where(detections.c.cls_name == cls_name)
        if since:
            stmt = stmt.where(detections.c.ts >= since.isoformat())
        if until:
            stmt = stmt.where(detections.c.ts <= until.isoformat())
        if ack_status:
            stmt = stmt.where(detections.c.ack_status == ack_status)
        out: dict[int, int] = {h: 0 for h in range(24)}
        with self._engine.begin() as conn:
            for (ts,) in conn.execute(stmt).all():
                try:
                    hour = int(str(ts)[11:13])
                    out[hour] = out.get(hour, 0) + 1
                except (ValueError, IndexError):
                    continue
        return out

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
            "display_label",
            "label_status",
            "label_source",
            "label_confidence",
            "reviewed_by",
            "reviewed_at",
            "review_note",
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

    def create_qa_session(self, values: dict) -> str:
        session_id = str(values["id"])
        with self._engine.begin() as conn:
            conn.execute(
                qa_sessions.insert().values(
                    id=session_id,
                    started_at=str(values["started_at"]),
                    completed_at=values.get("completed_at"),
                    phase=str(values["phase"]),
                    status=str(values.get("status", "running")),
                    repetitions=int(values["repetitions"]),
                    countdown_seconds=float(values["countdown_seconds"]),
                    scan_timeout_seconds=float(values["scan_timeout_seconds"]),
                    model_path=values.get("model_path"),
                    model_hash=values.get("model_hash"),
                    sample_count=int(values["sample_count"]),
                    config_json=json.dumps(
                        values.get("config", {}),
                        ensure_ascii=False,
                    ),
                )
            )
        return session_id

    def update_qa_session_status(
        self,
        session_id: str,
        status: str,
        *,
        completed_at: str | None = None,
    ) -> None:
        values: dict[str, str] = {"status": status}
        if completed_at is not None:
            values["completed_at"] = completed_at
        with self._engine.begin() as conn:
            conn.execute(
                qa_sessions.update()
                .where(qa_sessions.c.id == session_id)
                .values(**values)
            )

    def insert_qa_trial(self, values: dict) -> str:
        bbox = values.get("bbox") or (None, None, None, None)
        with self._engine.begin() as conn:
            conn.execute(
                qa_trials.insert().values(
                    id=str(values["id"]),
                    session_id=str(values["session_id"]),
                    sample_index=int(values["sample_index"]),
                    sample_label=str(values["sample_label"]),
                    expected_class=str(values["expected_class"]),
                    expected_route=str(values["expected_route"]),
                    trial_number=int(values["trial_number"]),
                    phase=str(values["phase"]),
                    started_at=str(values["started_at"]),
                    completed_at=str(values["completed_at"]),
                    verdict=str(values["verdict"]),
                    predicted_class=values.get("predicted_class"),
                    predicted_route=values.get("predicted_route"),
                    confidence=values.get("confidence"),
                    bbox_x1=bbox[0],
                    bbox_y1=bbox[1],
                    bbox_x2=bbox[2],
                    bbox_y2=bbox[3],
                    detection_count=int(values.get("detection_count", 0)),
                    raw_image_path=values.get("raw_image_path"),
                    annotated_image_path=values.get("annotated_image_path"),
                    meta_path=values.get("meta_path"),
                    guard_reason=values.get("guard_reason"),
                    speaker_mode=values.get("speaker_mode"),
                    uart_payload=values.get("uart_payload"),
                    ack_status=values.get("ack_status"),
                    rtt_ms=values.get("rtt_ms"),
                    model_hash=values.get("model_hash"),
                    promoted_path=values.get("promoted_path"),
                    extra_json=json.dumps(
                        values.get("extra", {}),
                        ensure_ascii=False,
                    ),
                )
            )
        return str(values["id"])

    def list_qa_sessions(self, limit: int = 100):
        stmt = select(qa_sessions).order_by(qa_sessions.c.started_at.desc()).limit(limit)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [HistoryRow(**dict(row)) for row in rows]

    def query_qa_trials(
        self,
        *,
        session_id: str | None = None,
        limit: int = 500,
    ):
        stmt = select(qa_trials).order_by(qa_trials.c.completed_at.desc()).limit(limit)
        if session_id:
            stmt = stmt.where(qa_trials.c.session_id == session_id)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [HistoryRow(**dict(row)) for row in rows]

    def get_qa_trial(self, trial_id: str):
        stmt = select(qa_trials).where(qa_trials.c.id == trial_id)
        with self._engine.begin() as conn:
            row = conn.execute(stmt).mappings().first()
        return HistoryRow(**dict(row)) if row is not None else None

    def mark_qa_trial_promoted(self, trial_id: str, promoted_path: str) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                qa_trials.update()
                .where(qa_trials.c.id == trial_id)
                .values(promoted_path=promoted_path)
            )

    def export_qa_session(self, session_id: str, out_path: Path) -> int:
        rows = self.query_qa_trials(session_id=session_id, limit=1_000_000)
        if out_path.suffix.lower() == ".json":
            payload = [dict(row.__dict__) for row in rows]
            out_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return len(rows)
        columns = [column.name for column in qa_trials.columns]
        with out_path.open("w", encoding="utf-8", newline="") as output:
            writer = csv.writer(output)
            writer.writerow(columns)
            for row in rows:
                writer.writerow([getattr(row, column, "") for column in columns])
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
