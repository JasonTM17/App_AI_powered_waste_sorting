"""Seed isolated local-agent data for Playwright QA runs.

This script intentionally writes only under web/.playwright-tmp by default.
It creates local test accounts, device config, and owned history rows so E2E
tests can exercise User/Admin RBAC without touching real app data.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ADMIN_USERNAME = "qa-admin"
ADMIN_PASSWORD = "QaAdmin#2026"
USER_USERNAME = "qa-user"
USER_PASSWORD = "QaUser#2026"
OTHER_USERNAME = "qa-other"
OTHER_PASSWORD = "QaOther#2026"
TEMP_USERNAME = "qa-temp-admin"
TEMP_PASSWORD = "QaTemp#2026"
DEVICE_ID = "qa-trash-sorter-001"


def main() -> None:
    tmp_root = _tmp_root()
    _reset_tmp_root(tmp_root)
    os.environ["APPDATA"] = str(tmp_root / "appdata")
    os.environ["XDG_CONFIG_HOME"] = str(tmp_root / "xdg")
    os.environ["TRASH_SORTER_AUTH_DEV_DEFAULTS"] = "0"
    os.environ.pop("TRASH_SORTER_AUTH_DATABASE_URL", None)
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME", None)
    os.environ.pop("TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD", None)

    from app.agent.auth_service import AuthService
    from app.core.config import AppConfig, save_config
    from app.core.dataset_catalog import DatasetCatalog
    from app.core.history import HistoryService
    from app.core.waste_categories import (
        category_for_class,
        default_class_id_for_name,
        make_three_bin_mappings,
    )
    from app.utils.paths import (
        app_data_dir,
        auth_db_path,
        config_path,
        dataset_db_path,
        db_path,
    )

    app_data = app_data_dir()
    auth_db = Path(os.getenv("TRASH_SORTER_AUTH_DB") or auth_db_path())
    os.environ["TRASH_SORTER_AUTH_DB"] = str(auth_db)

    cfg = AppConfig()
    cfg.device.device_id = DEVICE_ID
    cfg.device.device_name = "EcoSort QA Station"
    cfg.device.location = "QA Lab"
    cfg.device.owner_username = USER_USERNAME
    cfg.capture.output_dir = str(app_data / "dataset_v2")
    cfg.mappings = make_three_bin_mappings()
    save_config(cfg, config_path())

    service = AuthService(db_path=auth_db)
    _create_account(service, ADMIN_USERNAME, ADMIN_PASSWORD, "admin")
    _create_account(service, USER_USERNAME, USER_PASSWORD, "user")
    _create_account(service, OTHER_USERNAME, OTHER_PASSWORD, "user")
    _create_account(service, TEMP_USERNAME, TEMP_PASSWORD, "admin", password_default=True)
    accounts = {str(row["username"]): row for row in service.list_accounts()}

    image_dir = app_data / "qa_detection_images"
    image_dir.mkdir(parents=True, exist_ok=True)
    history = HistoryService(db_path())
    inserted_rows: list[int] = []
    try:
        owned_days = [
            (0, "Plastic bottle", 0.93),
            (0, "Organic", 0.9),
            (0, "Paper", 0.88),
            (1, "Banana peel", 0.91),
            (1, "Aluminum can", 0.92),
            (2, "Pen", 0.85),
            (3, "Cardboard", 0.89),
            (5, "Leftover food", 0.87),
            (8, "Plastic bottle", 0.94),
            (12, "Paper", 0.86),
            (18, "Battery", 0.82),
            (27, "Organic", 0.91),
            (35, "Milk carton", 0.88),
            (50, "Foam food box", 0.8),
            (76, "Textile", 0.84),
            (95, "Glass bottle", 0.9),
            (120, "Banana peel", 0.89),
            (155, "Disposable tableware", 0.81),
            (178, "Aluminum can", 0.93),
        ]
        user_id = int(accounts[USER_USERNAME]["id"])
        for index, (days_ago, cls_name, confidence) in enumerate(owned_days, start=1):
            inserted_rows.append(
                _insert_history_row(
                    history,
                    category_for_class=category_for_class,
                    default_class_id_for_name=default_class_id_for_name,
                    image_dir=image_dir,
                    track_id=index,
                    days_ago=days_ago,
                    cls_name=cls_name,
                    confidence=confidence,
                    owner_account_id=user_id,
                    owner_username=USER_USERNAME,
                )
            )

        other_id = int(accounts[OTHER_USERNAME]["id"])
        _insert_history_row(
            history,
            category_for_class=category_for_class,
            default_class_id_for_name=default_class_id_for_name,
            image_dir=image_dir,
            track_id=9001,
            days_ago=1,
            cls_name="Electronics",
            confidence=0.96,
            owner_account_id=other_id,
            owner_username=OTHER_USERNAME,
        )
        _insert_history_row(
            history,
            category_for_class=category_for_class,
            default_class_id_for_name=default_class_id_for_name,
            image_dir=image_dir,
            track_id=9002,
            days_ago=1,
            cls_name="Cigarette",
            confidence=0.77,
            owner_account_id=None,
            owner_username=None,
        )
    finally:
        history.close()

    dataset_db_path().parent.mkdir(parents=True, exist_ok=True)
    dataset_db_path().touch()
    dataset_catalog = DatasetCatalog(dataset_db_path())
    dataset_catalog.close()
    state = {
        "accounts": {
            "admin": {"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
            "user": {"username": USER_USERNAME, "password": USER_PASSWORD},
            "other": {"username": OTHER_USERNAME, "password": OTHER_PASSWORD},
            "temporary_admin": {"username": TEMP_USERNAME, "password": TEMP_PASSWORD},
        },
        "paths": {
            "tmp_root": str(tmp_root),
            "app_data": str(app_data),
            "auth_db": str(auth_db),
            "history_db": str(db_path()),
            "dataset_db": str(dataset_db_path()),
            "config": str(config_path()),
        },
        "seed": {
            "device_id": DEVICE_ID,
            "owned_history_rows": len(inserted_rows),
        },
    }
    (tmp_root / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def _tmp_root() -> Path:
    raw = os.getenv("TRASH_SORTER_PLAYWRIGHT_TMP", "").strip()
    return Path(raw).resolve() if raw else (WEB_ROOT / ".playwright-tmp").resolve()


def _reset_tmp_root(tmp_root: Path) -> None:
    web_root = WEB_ROOT.resolve()
    if tmp_root != web_root / ".playwright-tmp" and (web_root not in tmp_root.parents):
        raise RuntimeError(f"Refusing to delete Playwright tmp outside web root: {tmp_root}")
    shutil.rmtree(tmp_root, ignore_errors=True)
    tmp_root.mkdir(parents=True, exist_ok=True)


def _create_account(service, username: str, password: str, role: str, *, password_default: bool = False) -> None:
    try:
        service.create_account(username, password, role, password_default=password_default)
    except Exception as exc:
        if "UNIQUE" not in str(exc).upper() and "duplicate" not in str(exc).lower():
            raise


def _insert_history_row(
    history,
    *,
    category_for_class,
    default_class_id_for_name,
    image_dir: Path,
    track_id: int,
    days_ago: int,
    cls_name: str,
    confidence: float,
    owner_account_id: int | None,
    owner_username: str | None,
) -> int:
    category = category_for_class(cls_name)
    class_id = default_class_id_for_name(cls_name)
    raw_path = image_dir / f"{track_id:04d}-{_slug(cls_name)}-raw.jpg"
    annotated_path = image_dir / f"{track_id:04d}-{_slug(cls_name)}-annotated.jpg"
    _write_image(raw_path, cls_name, (232, 244, 236))
    _write_image(annotated_path, f"{cls_name} -> {category.name}", (218, 236, 255))
    ts = datetime.now(UTC) - timedelta(days=days_ago, hours=track_id % 9)
    return history.insert(
        track_id=track_id,
        ts=ts,
        cls_id=class_id if class_id is not None else track_id,
        cls_name=cls_name,
        conf=confidence,
        bbox=(12, 10, 116, 92),
        image_path=str(raw_path),
        annotated_path=str(annotated_path),
        route_label=category.name,
        bin_index=category.bin_index,
        uart_command=category.code,
        ack_status="ok",
        rtt_ms=110 + (track_id % 5) * 12,
        owner_account_id=owner_account_id,
        owner_username=owner_username,
        device_id=DEVICE_ID,
    )


def _write_image(path: Path, label: str, color: tuple[int, int, int]) -> None:
    image = Image.new("RGB", (220, 150), color)
    draw = ImageDraw.Draw(image)
    draw.rectangle((16, 16, 204, 134), outline=(24, 87, 54), width=3)
    draw.text((28, 62), label[:28], fill=(17, 24, 39))
    image.save(path, format="JPEG", quality=90)


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-") or "item"


if __name__ == "__main__":
    main()
