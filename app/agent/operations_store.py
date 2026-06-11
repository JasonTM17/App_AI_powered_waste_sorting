"""Local operations store for bin map, alerts, schedules, and issue reports."""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from threading import Lock, Thread
from uuid import uuid4

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    inspect,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Engine

from app.agent.auth_service import create_database_engine, normalize_database_url
from app.agent.schema_readiness import SchemaReadiness

metadata = MetaData()

devices = Table(
    "devices",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("device_id", String, nullable=False, unique=True),
    Column("device_name", String, nullable=False),
    Column("location", String, nullable=False, default=""),
    Column("owner_username", String, nullable=False, default=""),
    Column("status", String, nullable=False, default="offline"),
    Column("message", String, nullable=False, default=""),
    Column("active", Integer, nullable=False, default=1),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

bin_stations = Table(
    "bin_stations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("station_id", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("area", String, nullable=False, default=""),
    Column("address", String, nullable=False, default=""),
    Column("latitude", Float),
    Column("longitude", Float),
    Column("status", String, nullable=False, default="candidate"),
    Column("coordinate_verified", Integer, nullable=False, default=0),
    Column("source", String, nullable=False, default="local"),
    Column("assigned_owner_username", String, nullable=False, default=""),
    Column("active", Integer, nullable=False, default=1),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

bins = Table(
    "bins",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("bin_id", String, nullable=False, unique=True),
    Column("station_id", String, nullable=False),
    Column("command", String, nullable=False),
    Column("bin_index", Integer, nullable=False),
    Column("label", String, nullable=False),
    Column("fullness_percent", Float),
    Column("status", String, nullable=False, default="unknown"),
    Column("active", Integer, nullable=False, default=1),
    Column("updated_at", String, nullable=False),
)

collection_schedules = Table(
    "collection_schedules",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("schedule_id", String, nullable=False, unique=True),
    Column("station_id", String, nullable=False),
    Column("assigned_owner_username", String, nullable=False, default=""),
    Column("scheduled_date", String, nullable=False),
    Column("window_start", String, nullable=False, default="07:00"),
    Column("window_end", String, nullable=False, default="11:00"),
    Column("status", String, nullable=False, default="scheduled"),
    Column("completed_at", String),
    Column("completed_by", String, nullable=False, default=""),
    Column("note", String, nullable=False, default=""),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
)

collection_events = Table(
    "collection_events",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("event_id", String, nullable=False, unique=True),
    Column("schedule_id", String, nullable=False),
    Column("station_id", String, nullable=False),
    Column("actor_username", String, nullable=False),
    Column("actor_account_id", Integer),
    Column("completed_at", String, nullable=False),
    Column("note", String, nullable=False, default=""),
)

alerts = Table(
    "alerts",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("alert_id", String, nullable=False, unique=True),
    Column("station_id", String, nullable=False, default=""),
    Column("bin_id", String, nullable=False, default=""),
    Column("device_id", String, nullable=False, default=""),
    Column("severity", String, nullable=False, default="info"),
    Column("title", String, nullable=False),
    Column("message", String, nullable=False, default=""),
    Column("status", String, nullable=False, default="open"),
    Column("source", String, nullable=False, default="manual"),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("resolved_at", String, nullable=False, default=""),
    Column("actor_username", String, nullable=False, default=""),
)

device_issues = Table(
    "device_issues",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("issue_id", String, nullable=False, unique=True),
    Column("station_id", String, nullable=False, default=""),
    Column("bin_id", String, nullable=False, default=""),
    Column("device_id", String, nullable=False, default=""),
    Column("issue_type", String, nullable=False),
    Column("severity", String, nullable=False, default="warning"),
    Column("description", String, nullable=False, default=""),
    Column("status", String, nullable=False, default="open"),
    Column("reporter_username", String, nullable=False, default=""),
    Column("reporter_account_id", Integer),
    Column("alert_id", String, nullable=False, default=""),
    Column("created_at", String, nullable=False),
    Column("updated_at", String, nullable=False),
    Column("resolved_at", String, nullable=False, default=""),
)

DEFAULT_CENTER = {"latitude": 10.843195, "longitude": 106.777800, "zoom": 12}
SEED_SOURCE = "thu_duc_seed_2026_06_10"
DEFAULT_SEED_OWNER_USERNAME = "user"
DEFAULT_USER_STATION_COUNT = 2
_ENGINE_CACHE: dict[str, Engine] = {}
_ENGINE_LOCK = Lock()
_SCHEMA_READINESS = SchemaReadiness()
CHILD_BIN_SEEDS = [
    {"suffix": "O", "command": "O", "bin_index": 1, "label": "Huu co"},
    {"suffix": "R", "command": "R", "bin_index": 2, "label": "Vo co"},
    {"suffix": "I", "command": "I", "bin_index": 3, "label": "Tai che"},
]


def configured_operations_database_url() -> str:
    if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("TRASH_SORTER_TEST_ALLOW_OPERATIONS_DATABASE_URL") != "1":
        return ""
    raw = (
        os.environ.get("TRASH_SORTER_OPERATIONS_DATABASE_URL", "").strip()
        or os.environ.get("TRASH_SORTER_AUTH_DATABASE_URL", "").strip()
        or os.environ.get("DATABASE_URL", "").strip()
    )
    return normalize_database_url(raw)
THU_DUC_SEED_STATIONS = [
    {
        "station_id": "td-bin-001",
        "name": "Vincom Mega Mall Thao Dien",
        "latitude": 10.8020001,
        "longitude": 106.7406138,
        "area": "Thao Dien/An Khanh",
        "address": "Vincom Mega Mall Thao Dien, Song Hanh Vo Nguyen Giap",
    },
    {
        "station_id": "td-bin-002",
        "name": "GIGAMALL Thu Duc",
        "latitude": 10.8276722,
        "longitude": 106.7215390,
        "area": "Hiep Binh",
        "address": "Gigamall Thu Duc, Pham Van Dong",
    },
    {
        "station_id": "td-bin-003",
        "name": "Thu Duc Market",
        "latitude": 10.8502385,
        "longitude": 106.7541974,
        "area": "Linh Xuan",
        "address": "Cho Thu Duc, Ho Van Tu",
    },
    {
        "station_id": "td-bin-004",
        "name": "Suoi Tien Theme Park",
        "latitude": 10.8618947,
        "longitude": 106.8025939,
        "area": "Tang Nhon Phu",
        "address": "Khu du lich Suoi Tien, 120 Xa lo Ha Noi",
    },
    {
        "station_id": "td-bin-005",
        "name": "Saigon Hi-Tech Park",
        "latitude": 10.8379060,
        "longitude": 106.8104659,
        "area": "Long Binh/Tan Phu",
        "address": "Khu cong nghe cao Thanh pho Ho Chi Minh",
    },
    {
        "station_id": "td-bin-006",
        "name": "Nong Lam University HCMC",
        "latitude": 10.8723254,
        "longitude": 106.7889778,
        "area": "University area",
        "address": "Truong Dai hoc Nong Lam TP.HCM",
    },
    {
        "station_id": "td-bin-007",
        "name": "New Eastern Bus Station",
        "latitude": 10.8795958,
        "longitude": 106.8159644,
        "area": "Dong Hoa/Linh Trung edge",
        "address": "Ben xe Mien Dong Moi",
    },
    {
        "station_id": "td-bin-008",
        "name": "Metro National University Station",
        "latitude": 10.8660308,
        "longitude": 106.8003934,
        "area": "VNU-HCM area",
        "address": "Ga Metro Dai hoc Quoc gia",
    },
    {
        "station_id": "td-bin-009",
        "name": "Metro High-Tech Park Station",
        "latitude": 10.8587025,
        "longitude": 106.7886598,
        "area": "Hi-Tech Park corridor",
        "address": "Ga Metro Khu Cong Nghe Cao",
    },
    {
        "station_id": "td-bin-010",
        "name": "Thu Duc City People's Committee",
        "latitude": 10.7755847,
        "longitude": 106.7545988,
        "area": "Cat Lai/Thu Duc admin area",
        "address": "UBND Thanh pho Thu Duc",
    },
]


class OperationsStore:
    def __init__(
        self,
        db_path: Path,
        *,
        database_url: str | None = None,
        device_defaults: dict[str, str] | None = None,
    ):
        configured_url = database_url or configured_operations_database_url()
        self.db_path = db_path
        self.database_url = configured_url
        self._device_defaults = dict(device_defaults or {})
        if configured_url:
            self._engine = _shared_database_engine(configured_url)
            self._dispose_on_close = False
        else:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._engine: Engine = create_engine(f"sqlite:///{db_path}", future=True)
            self._dispose_on_close = True

    def seed_defaults(self, *, device_defaults: dict[str, str]) -> None:
        self.ensure_ready()
        self._seed_defaults(device_defaults=device_defaults)

    def _seed_defaults(self, *, device_defaults: dict[str, str]) -> None:
        now = _now()
        device_id = _clean(device_defaults.get("device_id")) or "local-trash-sorter"
        device_name = _clean(device_defaults.get("device_name")) or "Trash Sorter Local"
        location = _clean(device_defaults.get("location")) or "Thu Duc local seed"
        owner_username = _clean(device_defaults.get("owner_username")) or DEFAULT_SEED_OWNER_USERNAME
        today = date.today().isoformat()
        with self._engine.begin() as conn:
            conn.execute(
                self._insert_do_nothing(devices)
                .values(
                    device_id=device_id,
                    device_name=device_name,
                    location=location,
                    owner_username=owner_username,
                    status="offline",
                    message="Seeded local operations device.",
                    active=1,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["device_id"])
            )
            for index, station in enumerate(THU_DUC_SEED_STATIONS):
                station_id = station["station_id"]
                station_owner = owner_username if index < DEFAULT_USER_STATION_COUNT else ""
                conn.execute(
                    self._insert_do_nothing(bin_stations)
                    .values(
                        **station,
                        status="candidate",
                        coordinate_verified=0,
                        source=SEED_SOURCE,
                        assigned_owner_username=station_owner,
                        active=1,
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["station_id"])
                )
                for child in CHILD_BIN_SEEDS:
                    bin_id = f"{station_id}-{child['suffix']}"
                    conn.execute(
                        self._insert_do_nothing(bins)
                        .values(
                            bin_id=bin_id,
                            station_id=station_id,
                            command=child["command"],
                            bin_index=child["bin_index"],
                            label=child["label"],
                            fullness_percent=None,
                            status="unknown",
                            active=1,
                            updated_at=now,
                        )
                        .on_conflict_do_nothing(index_elements=["bin_id"])
                    )
                schedule_id = f"sched-{station_id}-seed"
                conn.execute(
                    self._insert_do_nothing(collection_schedules)
                    .values(
                        schedule_id=schedule_id,
                        station_id=station_id,
                        assigned_owner_username=station_owner,
                        scheduled_date=today,
                        window_start="07:00",
                        window_end="11:00",
                        status="scheduled",
                        completed_at=None,
                        completed_by="",
                        note="Seed collection schedule for local map MVP.",
                        created_at=now,
                        updated_at=now,
                    )
                    .on_conflict_do_nothing(index_elements=["schedule_id"])
                )
            assigned_seed_ids = [station["station_id"] for station in THU_DUC_SEED_STATIONS[:DEFAULT_USER_STATION_COUNT]]
            conn.execute(
                bin_stations.update()
                .where(bin_stations.c.station_id.in_(assigned_seed_ids))
                .where(bin_stations.c.assigned_owner_username == "")
                .values(assigned_owner_username=owner_username, updated_at=now)
            )
            conn.execute(
                collection_schedules.update()
                .where(collection_schedules.c.station_id.in_(assigned_seed_ids))
                .where(collection_schedules.c.assigned_owner_username == "")
                .values(assigned_owner_username=owner_username, updated_at=now)
            )

    def list_role_catalog(self) -> list[dict[str, object]]:
        from app.agent.auth import ADMIN_CAPABILITIES, USER_CAPABILITIES

        return [
            {
                "role": "admin",
                "label": "Admin",
                "capabilities": list(ADMIN_CAPABILITIES),
                "description": "Full local operations, config, report, and account management.",
            },
            {
                "role": "user",
                "label": "User",
                "capabilities": list(USER_CAPABILITIES),
                "description": "Scoped field operations: map, alerts, schedule, collection, issue report.",
            },
        ]

    def list_devices(self) -> list[dict[str, object]]:
        self.ensure_ready()
        with self._engine.begin() as conn:
            rows = conn.execute(select(devices).order_by(devices.c.device_name)).mappings().all()
        return [_device_dict(row) for row in rows]

    def upsert_device(self, values: dict[str, object]) -> dict[str, object]:
        self.ensure_ready()
        now = _now()
        device_id = _clean(values.get("device_id")) or "local-trash-sorter"
        payload = {
            "device_id": device_id,
            "device_name": _clean(values.get("device_name")) or device_id,
            "location": _clean(values.get("location")),
            "owner_username": _clean(values.get("owner_username")),
            "status": _clean(values.get("status")) or "offline",
            "message": _clean(values.get("message")),
            "active": 1 if values.get("active", True) else 0,
            "updated_at": now,
        }
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(devices.c.id).where(devices.c.device_id == device_id)
            ).scalar_one_or_none()
            if existing is None:
                conn.execute(devices.insert().values(**payload, created_at=now))
            else:
                conn.execute(devices.update().where(devices.c.id == existing).values(**payload))
        return self.get_device(device_id) or {}

    def get_device(self, device_id: str) -> dict[str, object] | None:
        self.ensure_ready()
        with self._engine.begin() as conn:
            row = conn.execute(
                select(devices).where(devices.c.device_id == device_id)
            ).mappings().first()
        return _device_dict(row) if row is not None else None

    def list_bin_map(
        self,
        *,
        owner_username: str | None = None,
        include_inactive: bool = False,
    ) -> dict[str, object]:
        self.ensure_ready()
        stations = self._station_rows(owner_username=owner_username, include_inactive=include_inactive)
        station_ids = [str(row["station_id"]) for row in stations]
        child_bins = self._bins_by_station(station_ids)
        alerts_by_station = self._alert_counts_by_station(station_ids, owner_username=owner_username)
        return {
            "generated_at": _now(),
            "center": dict(DEFAULT_CENTER),
            "stations": [
                _station_dict(row, child_bins.get(str(row["station_id"]), []), alerts_by_station)
                for row in stations
            ],
            "total": len(stations),
            "seed_source": SEED_SOURCE,
        }

    def create_station(self, values: dict[str, object]) -> dict[str, object]:
        self.ensure_ready()
        now = _now()
        station_id = _clean(values.get("station_id")) or f"custom-{uuid4().hex[:10]}"
        payload = _station_values(values, station_id=station_id, now=now)
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(bin_stations.c.id).where(bin_stations.c.station_id == station_id)
            ).scalar_one_or_none()
            if existing is not None:
                raise ValueError("station already exists")
            conn.execute(bin_stations.insert().values(**payload, created_at=now))
            for child in CHILD_BIN_SEEDS:
                conn.execute(
                    bins.insert().values(
                        bin_id=f"{station_id}-{child['suffix']}",
                        station_id=station_id,
                        command=child["command"],
                        bin_index=child["bin_index"],
                        label=child["label"],
                        fullness_percent=None,
                        status="unknown",
                        active=1,
                        updated_at=now,
                    )
                )
        return self.get_station(station_id, include_inactive=True) or {}

    def patch_station(self, station_id: str, values: dict[str, object]) -> dict[str, object] | None:
        self.ensure_ready()
        existing = self.get_station(station_id, include_inactive=True)
        if existing is None:
            return None
        now = _now()
        update_values = _station_patch_values(values, now=now)
        if not update_values:
            return existing
        with self._engine.begin() as conn:
            conn.execute(
                bin_stations.update()
                .where(bin_stations.c.station_id == station_id)
                .values(**update_values)
            )
        return self.get_station(station_id, include_inactive=True)

    def get_station(self, station_id: str, *, include_inactive: bool = False) -> dict[str, object] | None:
        self.ensure_ready()
        with self._engine.begin() as conn:
            stmt = select(bin_stations).where(bin_stations.c.station_id == station_id)
            if not include_inactive:
                stmt = stmt.where(bin_stations.c.active == 1)
            row = conn.execute(stmt).mappings().first()
        if row is None:
            return None
        child_bins = self._bins_by_station([station_id]).get(station_id, [])
        alerts_by_station = self._alert_counts_by_station([station_id], owner_username=None)
        return _station_dict(row, child_bins, alerts_by_station)

    def delete_station(self, station_id: str) -> bool:
        self.ensure_ready()
        return self.patch_station(station_id, {"active": False, "status": "inactive"}) is not None

    def update_bin_fullness(
        self,
        bin_index: int,
        percent: int | float,
        *,
        station_id: str = "",
        device_id: str = "",
        owner_username: str = "",
    ) -> dict[str, object] | None:
        self.ensure_ready()
        if bin_index < 1 or bin_index > len(CHILD_BIN_SEEDS):
            return None
        resolved_station_id = self._resolve_station_id(
            station_id=station_id,
            device_id=device_id,
            owner_username=owner_username,
        )
        if not resolved_station_id:
            return None
        clamped = max(0.0, min(100.0, float(percent)))
        now = _now()
        with self._engine.begin() as conn:
            result = conn.execute(
                bins.update()
                .where(bins.c.station_id == resolved_station_id)
                .where(bins.c.bin_index == bin_index)
                .where(bins.c.active == 1)
                .values(
                    fullness_percent=clamped,
                    status=_fullness_status(clamped),
                    updated_at=now,
                )
            )
            if result.rowcount == 0:
                return None
        return self.get_station(resolved_station_id, include_inactive=True)

    def list_alerts(
        self,
        *,
        owner_username: str | None = None,
        include_resolved: bool = True,
    ) -> list[dict[str, object]]:
        self.ensure_ready()
        station_ids = {
            str(row["station_id"])
            for row in self._station_rows(owner_username=owner_username, include_inactive=False)
        }
        with self._engine.begin() as conn:
            stmt = select(alerts).order_by(alerts.c.id.desc())
            if not include_resolved:
                stmt = stmt.where(alerts.c.status != "resolved")
            rows = conn.execute(stmt).mappings().all()
        scoped = [
            _alert_dict(row)
            for row in rows
            if not owner_username or not row["station_id"] or row["station_id"] in station_ids
        ]
        derived = self._derived_alerts(owner_username=owner_username)
        if include_resolved:
            return [*derived, *scoped]
        return [*derived, *[item for item in scoped if item["status"] != "resolved"]]

    def patch_alert(
        self,
        alert_id: str,
        *,
        status: str,
        actor_username: str = "",
    ) -> dict[str, object] | None:
        self.ensure_ready()
        now = _now()
        resolved_at = now if status == "resolved" else ""
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(alerts.c.id).where(alerts.c.alert_id == alert_id)
            ).scalar_one_or_none()
            if existing is None:
                return None
            conn.execute(
                alerts.update()
                .where(alerts.c.id == existing)
                .values(
                    status=status,
                    actor_username=actor_username,
                    updated_at=now,
                    resolved_at=resolved_at,
                )
            )
            row = conn.execute(select(alerts).where(alerts.c.id == existing)).mappings().first()
        return _alert_dict(row) if row is not None else None

    def list_schedules(self, *, owner_username: str | None = None) -> list[dict[str, object]]:
        self.ensure_ready()
        station_rows = self._station_rows(owner_username=owner_username, include_inactive=False)
        station_by_id = {str(row["station_id"]): _station_dict(row, []) for row in station_rows}
        station_ids = set(station_by_id)
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(collection_schedules).order_by(
                    collection_schedules.c.scheduled_date.asc(),
                    collection_schedules.c.window_start.asc(),
                )
            ).mappings().all()
        return [
            _schedule_dict(row, station_by_id.get(str(row["station_id"])))
            for row in rows
            if str(row["station_id"]) in station_ids
            and _assigned_to_scope(str(row["assigned_owner_username"] or ""), owner_username)
        ]

    def complete_collection(
        self,
        schedule_id: str,
        *,
        actor_username: str,
        actor_account_id: int | None,
        note: str = "",
    ) -> dict[str, object] | None:
        self.ensure_ready()
        now = _now()
        with self._engine.begin() as conn:
            criteria = collection_schedules.c.schedule_id == schedule_id
            if schedule_id.isdigit():
                criteria = or_(criteria, collection_schedules.c.id == int(schedule_id))
            row = conn.execute(select(collection_schedules).where(criteria)).mappings().first()
            if row is None:
                return None
            existing_completed = bool(row["completed_at"])
            existing_event = conn.execute(
                select(collection_events).where(
                    collection_events.c.schedule_id == row["schedule_id"]
                )
            ).mappings().first()
            if existing_event is None:
                conn.execute(
                    collection_events.insert().values(
                        event_id=f"evt-{uuid4().hex[:12]}",
                        schedule_id=row["schedule_id"],
                        station_id=row["station_id"],
                        actor_username=actor_username,
                        actor_account_id=actor_account_id,
                        completed_at=now,
                        note=note,
                    )
                )
            completed_at = row["completed_at"] or now
            completed_by = row["completed_by"] or actor_username
            conn.execute(
                collection_schedules.update()
                .where(collection_schedules.c.schedule_id == row["schedule_id"])
                .values(
                    status="completed",
                    completed_at=completed_at,
                    completed_by=completed_by,
                    note=note or row["note"],
                    updated_at=now,
                )
            )
            updated = conn.execute(
                select(collection_schedules).where(
                    collection_schedules.c.schedule_id == row["schedule_id"]
                )
            ).mappings().first()
        station = self.get_station(str(updated["station_id"])) if updated is not None else None
        if updated is None:
            return None
        result = _schedule_dict(updated, station)
        result["already_completed"] = bool(existing_event is not None or existing_completed)
        return result

    def create_issue(
        self,
        values: dict[str, object],
        *,
        reporter_username: str,
        reporter_account_id: int | None,
    ) -> dict[str, object]:
        self.ensure_ready()
        now = _now()
        issue_id = f"issue-{uuid4().hex[:12]}"
        alert_id = f"alert-{uuid4().hex[:12]}"
        station_id = _clean(values.get("station_id"))
        bin_id = _clean(values.get("bin_id"))
        device_id = _clean(values.get("device_id"))
        issue_type = _clean(values.get("issue_type")) or "other"
        severity = _clean(values.get("severity")) or "warning"
        description = _clean(values.get("description"))
        title = _issue_title(issue_type)
        with self._engine.begin() as conn:
            conn.execute(
                alerts.insert().values(
                    alert_id=alert_id,
                    station_id=station_id,
                    bin_id=bin_id,
                    device_id=device_id,
                    severity=severity,
                    title=title,
                    message=description,
                    status="open",
                    source="device_issue",
                    created_at=now,
                    updated_at=now,
                    resolved_at="",
                    actor_username=reporter_username,
                )
            )
            conn.execute(
                device_issues.insert().values(
                    issue_id=issue_id,
                    station_id=station_id,
                    bin_id=bin_id,
                    device_id=device_id,
                    issue_type=issue_type,
                    severity=severity,
                    description=description,
                    status="open",
                    reporter_username=reporter_username,
                    reporter_account_id=reporter_account_id,
                    alert_id=alert_id,
                    created_at=now,
                    updated_at=now,
                    resolved_at="",
                )
            )
            row = conn.execute(
                select(device_issues).where(device_issues.c.issue_id == issue_id)
            ).mappings().first()
        return _issue_dict(row) if row is not None else {}

    def summary(self, *, owner_username: str | None = None) -> dict[str, object]:
        self.ensure_ready()
        map_data = self.list_bin_map(owner_username=owner_username, include_inactive=False)
        schedules = self.list_schedules(owner_username=owner_username)
        alerts_list = self.list_alerts(owner_username=owner_username, include_resolved=False)
        issue_counts = self._issue_counts(owner_username=owner_username)
        return {
            "station_total": map_data["total"],
            "candidate_total": sum(
                1 for item in map_data["stations"] if item.get("status") == "candidate"
            ),
            "verified_total": sum(
                1 for item in map_data["stations"] if item.get("coordinate_verified")
            ),
            "alert_counts": _count_by(alerts_list, "severity"),
            "open_alert_total": len(alerts_list),
            "schedule_counts": _count_by(schedules, "state"),
            "issue_counts": issue_counts,
        }

    def health(self) -> dict[str, object]:
        self.ensure_ready()
        with self._engine.begin() as conn:
            station_total = int(conn.execute(select(func.count()).select_from(bin_stations)).scalar_one())
            bin_total = int(conn.execute(select(func.count()).select_from(bins)).scalar_one())
            schedule_total = int(
                conn.execute(select(func.count()).select_from(collection_schedules)).scalar_one()
            )
        return {
            "ok": station_total >= len(THU_DUC_SEED_STATIONS) and bin_total >= 30,
            "path": self._store_location(),
            "station_total": station_total,
            "bin_total": bin_total,
            "schedule_total": schedule_total,
            "seed_source": SEED_SOURCE,
        }

    def close(self) -> None:
        if self._dispose_on_close:
            self._engine.dispose()

    def ensure_ready(self) -> None:
        init_key = self.database_url or str(self.db_path.resolve())
        if (
            not self.database_url
            and _SCHEMA_READINESS.is_ready(init_key)
            and (not self.db_path.exists() or not _sqlite_schema_ready(self._engine))
        ):
            _SCHEMA_READINESS.reset(init_key)

        def _bootstrap() -> None:
            metadata.create_all(self._engine)
            with self._engine.begin() as conn:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bin_stations_active ON bin_stations(active)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_bins_station ON bins(station_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_schedules_station ON collection_schedules(station_id)"))
            self._seed_defaults(device_defaults=self._device_defaults)

        _SCHEMA_READINESS.ensure(init_key, _bootstrap)

    def _initialize_store(self, *, device_defaults: dict[str, str]) -> None:
        self._device_defaults = dict(device_defaults)
        self.ensure_ready()

    def _insert_do_nothing(self, table):
        if self._engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as postgres_insert

            return postgres_insert(table)
        return sqlite_insert(table)

    def _store_location(self) -> str:
        if self.database_url:
            return f"{self._engine.dialect.name}:configured"
        return str(self.db_path)



def _sqlite_schema_ready(engine: Engine) -> bool:
    if engine.dialect.name != "sqlite":
        return True
    inspector = inspect(engine)
    required_tables = ("bin_stations", "bins", "alerts", "collection_schedules")
    return all(inspector.has_table(table_name) for table_name in required_tables)


def _shared_database_engine(database_url: str) -> Engine:
    with _ENGINE_LOCK:
        engine = _ENGINE_CACHE.get(database_url)
        if engine is None:
            engine = create_database_engine(database_url)
            _ENGINE_CACHE[database_url] = engine
        return engine


def ensure_operations_schema_ready(
    db_path: Path,
    *,
    database_url: str | None = None,
    device_defaults: dict[str, str] | None = None,
) -> None:
    store = OperationsStore(
        db_path,
        database_url=database_url,
        device_defaults=device_defaults,
    )
    try:
        store.ensure_ready()
    finally:
        store.close()


def prewarm_operations_schema_async(
    db_path: Path,
    *,
    database_url: str | None = None,
    device_defaults: dict[str, str] | None = None,
) -> Thread:
    def _worker() -> None:
        try:
            ensure_operations_schema_ready(
                db_path,
                database_url=database_url,
                device_defaults=device_defaults,
            )
        except Exception:
            return

    thread = Thread(target=_worker, name="operations-schema-prewarm", daemon=True)
    thread.start()
    return thread


def _station_rows(
    self,
    *,
    owner_username: str | None,
    include_inactive: bool,
) -> list[dict[str, object]]:
    with self._engine.begin() as conn:
        stmt = select(bin_stations).order_by(bin_stations.c.station_id)
        if not include_inactive:
            stmt = stmt.where(bin_stations.c.active == 1)
        if owner_username:
            stmt = stmt.where(bin_stations.c.assigned_owner_username == owner_username)
        return [dict(row) for row in conn.execute(stmt).mappings().all()]


def _bins_by_station(self, station_ids: list[str]) -> dict[str, list[dict[str, object]]]:
    if not station_ids:
        return {}
    with self._engine.begin() as conn:
        rows = conn.execute(
            select(bins)
            .where(bins.c.station_id.in_(station_ids))
            .order_by(bins.c.station_id, bins.c.bin_index)
        ).mappings().all()
    out: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        out.setdefault(str(row["station_id"]), []).append(_bin_dict(row))
    return out


def _alert_counts_by_station(
    self,
    station_ids: list[str],
    *,
    owner_username: str | None,
) -> dict[str, dict[str, int]]:
    if not station_ids:
        return {}
    alert_rows = self.list_alerts(owner_username=owner_username, include_resolved=False)
    out: dict[str, dict[str, int]] = {}
    for alert in alert_rows:
        station_id = str(alert.get("station_id") or "")
        if station_id not in station_ids:
            continue
        severity = str(alert.get("severity") or "info")
        out.setdefault(station_id, {})
        out[station_id][severity] = out[station_id].get(severity, 0) + 1
    return out


def _derived_alerts(self, *, owner_username: str | None) -> list[dict[str, object]]:
    stations = self._station_rows(owner_username=owner_username, include_inactive=False)
    station_ids = [str(row["station_id"]) for row in stations]
    child_bins = [item for values in self._bins_by_station(station_ids).values() for item in values]
    out: list[dict[str, object]] = []
    generated_at = _now()
    for item in child_bins:
        fullness = item.get("fullness_percent")
        if not isinstance(fullness, int | float):
            continue
        if fullness >= 95:
            severity = "danger"
        elif fullness >= 80:
            severity = "warning"
        else:
            continue
        out.append(
            {
                "alert_id": f"derived-fullness-{item['bin_id']}",
                "station_id": item["station_id"],
                "bin_id": item["bin_id"],
                "device_id": "",
                "severity": severity,
                "title": "Th?ng r?c g?n ??y",
                "message": f"{item['label']} ?ang ??y {round(float(fullness))}%.",
                "status": "open",
                "source": "derived_fullness",
                "created_at": generated_at,
                "updated_at": generated_at,
                "resolved_at": "",
                "actor_username": "",
                "derived": True,
            }
        )
    return out


def _issue_counts(self, *, owner_username: str | None) -> dict[str, int]:
    station_ids = {
        str(row["station_id"])
        for row in self._station_rows(owner_username=owner_username, include_inactive=False)
    }
    with self._engine.begin() as conn:
        rows = conn.execute(select(device_issues)).mappings().all()
    filtered = [
        _issue_dict(row)
        for row in rows
        if not owner_username or not row["station_id"] or row["station_id"] in station_ids
    ]
    return _count_by(filtered, "issue_type")


def _resolve_station_id(self, *, station_id: str, device_id: str, owner_username: str) -> str:
    station_id = _clean(station_id)
    if station_id and self.get_station(station_id) is not None:
        return station_id

    owner_username = _clean(owner_username)
    device_id = _clean(device_id)
    if not owner_username and device_id:
        device = self.get_device(device_id)
        if device:
            owner_username = _clean(device.get("owner_username"))

    rows = self._station_rows(
        owner_username=owner_username or None,
        include_inactive=False,
    )
    if rows:
        return str(rows[0]["station_id"])
    return ""


OperationsStore._station_rows = _station_rows
OperationsStore._bins_by_station = _bins_by_station
OperationsStore._alert_counts_by_station = _alert_counts_by_station
OperationsStore._derived_alerts = _derived_alerts
OperationsStore._issue_counts = _issue_counts
OperationsStore._resolve_station_id = _resolve_station_id


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _bool(value: object) -> bool:
    return bool(int(value or 0))


def _fullness_status(fullness: float | None) -> str:
    if fullness is None:
        return "unknown"
    if fullness >= 95:
        return "full"
    if fullness >= 80:
        return "warning"
    return "normal"


def _device_dict(row) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "device_id": str(row["device_id"]),
        "device_name": str(row["device_name"]),
        "location": str(row["location"] or ""),
        "owner_username": str(row["owner_username"] or ""),
        "status": str(row["status"] or "offline"),
        "message": str(row["message"] or ""),
        "active": _bool(row["active"]),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def _bin_dict(row) -> dict[str, object]:
    fullness = row["fullness_percent"]
    fill_percent = float(fullness) if isinstance(fullness, int | float) else 0.0
    return {
        "id": int(row["id"]),
        "bin_id": str(row["bin_id"]),
        "station_id": str(row["station_id"]),
        "command": str(row["command"]),
        "bin_index": int(row["bin_index"]),
        "label": str(row["label"]),
        "fullness_percent": fullness,
        "fill_percent": fill_percent,
        "status": _fullness_status(fill_percent) if fullness is not None else str(row["status"] or "unknown"),
        "active": _bool(row["active"]),
        "updated_at": str(row["updated_at"] or ""),
    }


def _station_dict(
    row,
    child_bins: list[dict[str, object]],
    alerts_by_station: dict[str, dict[str, int]] | None = None,
) -> dict[str, object]:
    station_id = str(row["station_id"])
    alert_counts = (alerts_by_station or {}).get(station_id, {})
    open_alert_total = sum(alert_counts.values())
    assigned_owner = str(row["assigned_owner_username"] or "")
    source = str(row["source"] or "")
    return {
        "id": int(row["id"]),
        "station_id": station_id,
        "name": str(row["name"]),
        "area": str(row["area"] or ""),
        "address": str(row["address"] or ""),
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "status": str(row["status"] or "candidate"),
        "coordinate_verified": _bool(row["coordinate_verified"]),
        "source": source,
        "seed_source": source,
        "assigned_owner_username": assigned_owner,
        "owner_username": assigned_owner,
        "device_id": "",
        "note": "",
        "active": _bool(row["active"]),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
        "bins": child_bins,
        "alert_counts": alert_counts,
        "alert_total": open_alert_total,
        "open_alert_total": open_alert_total,
    }


def _station_values(values: dict[str, object], *, station_id: str, now: str) -> dict[str, object]:
    return {
        "station_id": station_id,
        "name": _clean(values.get("name")) or station_id,
        "area": _clean(values.get("area")),
        "address": _clean(values.get("address")),
        "latitude": values.get("latitude"),
        "longitude": values.get("longitude"),
        "status": _clean(values.get("status")) or "candidate",
        "coordinate_verified": 1 if values.get("coordinate_verified") else 0,
        "source": _clean(values.get("source")) or "admin",
        "assigned_owner_username": _clean(values.get("assigned_owner_username") or values.get("owner_username")),
        "active": 1 if values.get("active", True) else 0,
        "updated_at": now,
    }


def _station_patch_values(values: dict[str, object], *, now: str) -> dict[str, object]:
    allowed = {
        "name",
        "area",
        "address",
        "latitude",
        "longitude",
        "status",
        "coordinate_verified",
        "source",
        "assigned_owner_username",
        "owner_username",
        "active",
    }
    out: dict[str, object] = {}
    for key, value in values.items():
        if key not in allowed or value is None:
            continue
        if key in {"coordinate_verified", "active"}:
            out[key] = 1 if value else 0
        elif key in {"latitude", "longitude"}:
            out[key] = value
        elif key == "owner_username":
            out["assigned_owner_username"] = _clean(value)
        else:
            out[key] = _clean(value)
    if out:
        out["updated_at"] = now
    return out


def _alert_dict(row) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "alert_id": str(row["alert_id"]),
        "station_id": str(row["station_id"] or ""),
        "bin_id": str(row["bin_id"] or ""),
        "device_id": str(row["device_id"] or ""),
        "severity": str(row["severity"] or "info"),
        "title": str(row["title"]),
        "message": str(row["message"] or ""),
        "status": str(row["status"] or "open"),
        "source": str(row["source"] or "manual"),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
        "resolved_at": str(row["resolved_at"] or ""),
        "actor_username": str(row["actor_username"] or ""),
        "derived": False,
    }


def _schedule_dict(row, station: dict[str, object] | None) -> dict[str, object]:
    scheduled_date = str(row["scheduled_date"])
    state = str(row["status"] or "scheduled")
    if state == "scheduled" and row["completed_at"]:
        state = "completed"
    elif state == "scheduled":
        today = date.today().isoformat()
        if scheduled_date < today:
            state = "overdue"
        elif scheduled_date == today:
            state = "due_today"
        else:
            state = "upcoming"
    return {
        "id": int(row["id"]),
        "schedule_id": str(row["schedule_id"]),
        "station_id": str(row["station_id"]),
        "station_name": str((station or {}).get("name") or row["station_id"]),
        "assigned_owner_username": str(row["assigned_owner_username"] or ""),
        "scheduled_date": scheduled_date,
        "window_start": str(row["window_start"] or ""),
        "window_end": str(row["window_end"] or ""),
        "status": str(row["status"] or "scheduled"),
        "state": state,
        "completed_at": row["completed_at"],
        "completed_by": str(row["completed_by"] or ""),
        "note": str(row["note"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
    }


def _issue_dict(row) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "issue_id": str(row["issue_id"]),
        "station_id": str(row["station_id"] or ""),
        "bin_id": str(row["bin_id"] or ""),
        "device_id": str(row["device_id"] or ""),
        "issue_type": str(row["issue_type"] or "other"),
        "severity": str(row["severity"] or "warning"),
        "description": str(row["description"] or ""),
        "status": str(row["status"] or "open"),
        "reporter_username": str(row["reporter_username"] or ""),
        "reporter_account_id": row["reporter_account_id"],
        "alert_id": str(row["alert_id"] or ""),
        "created_at": str(row["created_at"] or ""),
        "updated_at": str(row["updated_at"] or ""),
        "resolved_at": str(row["resolved_at"] or ""),
    }


def _assigned_to_scope(assigned_owner: str, owner_username: str | None) -> bool:
    return not owner_username or assigned_owner == owner_username


def _issue_title(issue_type: str) -> str:
    labels = {
        "full_bin": "Báo đầy thùng rác",
        "sensor_problem": "Lỗi cảm biến",
        "camera_problem": "Lỗi camera",
        "servo_problem": "Lỗi servo",
        "audio_problem": "Lỗi âm thanh",
        "dirty_bin": "Thùng rác cần vệ sinh",
        "other": "Báo lỗi thiết bị",
    }
    return labels.get(issue_type, labels["other"])


def _count_by(rows: list[dict[str, object]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        out[value] = out.get(value, 0) + 1
    return out


__all__ = [
    "DEFAULT_CENTER",
    "DEFAULT_SEED_OWNER_USERNAME",
    "SEED_SOURCE",
    "THU_DUC_SEED_STATIONS",
    "OperationsStore",
    "configured_operations_database_url",
    "ensure_operations_schema_ready",
    "prewarm_operations_schema_async",
]
