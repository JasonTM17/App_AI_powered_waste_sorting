import json
import zipfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from PIL import Image
from starlette.routing import WebSocketRoute
from starlette.websockets import WebSocketDisconnect

from app.agent import api as api_module
from app.agent.api import create_app
from app.agent.auth_service import AuthService
from app.agent.runtime import AgentRuntime
from app.core.config import AppConfig, save_config
from app.core.dataset_catalog import DatasetCatalog
from app.core.history import HistoryService

ADMIN_USERNAME = "qa-admin"
ADMIN_PASSWORD = "qa-admin-pass-123"
USER_USERNAME = "qa-user"
USER_PASSWORD = "qa-user-pass-123"

EXPECTED_AGENT_ROUTES = {
    "GET /api/health",
    "POST /api/auth/login",
    "POST /api/auth/logout",
    "POST /api/auth/change-password",
    "GET /api/me",
    "GET /api/user/dashboard",
    "GET /api/user/analytics",
    "GET /api/user/device",
    "GET /api/user/report",
    "GET /api/user/experience",
    "GET /api/user/history",
    "GET /api/user/history/export.csv",
    "GET /api/user/history/{row_id}/image",
    "GET /api/user/bin-map",
    "GET /api/user/alerts",
    "GET /api/user/collection-schedule",
    "POST /api/user/collections/{schedule_id}/complete",
    "POST /api/user/device-issues",
    "POST /api/user/advisor",
    "POST /api/user/chat",
    "GET /api/admin/roles",
    "GET /api/admin/devices",
    "POST /api/admin/devices",
    "GET /api/admin/bin-map",
    "POST /api/admin/bin-map",
    "PATCH /api/admin/bin-map/{station_id}",
    "DELETE /api/admin/bin-map/{station_id}",
    "GET /api/admin/alerts",
    "PATCH /api/admin/alerts/{alert_id}",
    "GET /api/admin/collection-schedules",
    "GET /api/admin/operations/health",
    "GET /api/admin/accounts",
    "POST /api/admin/accounts",
    "POST /api/admin/accounts/{username}/reset-password",
    "PATCH /api/admin/accounts/{username}",
    "POST /api/admin/history/backfill-owner",
    "GET /api/admin/knowledge",
    "POST /api/admin/knowledge",
    "PATCH /api/admin/knowledge/{entry_id}",
    "POST /api/admin/knowledge/reload",
    "POST /api/admin/knowledge/evaluate",
    "POST /api/admin/chat",
    "GET /api/status",
    "GET /api/hardware/profile",
    "POST /api/hardware/test",
    "POST /api/hardware/audio-test",
    "POST /api/hardware/mp3-test",
    "POST /api/hardware/servo-angle",
    "POST /api/hardware/home-angle",
    "POST /api/hardware/sort-angle",
    "GET /api/hardware/diagnostics",
    "POST /api/hardware/reconnect",
    "GET /api/actuation/test-mode",
    "PUT /api/actuation/test-mode",
    "POST /api/devices/refresh",
    "POST /api/camera/start",
    "POST /api/camera/stop",
    "GET /api/camera/stream",
    "GET /api/settings",
    "PUT /api/settings",
    "GET /api/mappings",
    "PUT /api/mappings",
    "GET /api/model/classes",
    "GET /api/common-waste/catalog",
    "GET /api/training/status",
    "GET /api/learn-now/status",
    "GET /api/dataset/source-quality",
    "POST /api/learn-now/refresh-references",
    "POST /api/learn-now/unknown/capture",
    "POST /api/learn-now/micro-train/start",
    "GET /api/history",
    "GET /api/history/export.csv",
    "GET /api/history/{row_id}/image",
    "GET /api/dataset/summary",
    "GET /api/dataset/items",
    "GET /api/dataset/items/{item_id}",
    "GET /api/dataset/items/{item_id}/image",
    "PUT /api/dataset/items/{item_id}/boxes",
    "POST /api/dataset/sync",
    "POST /api/dataset/import",
    "POST /api/dataset/manual",
    "POST /api/dataset/camera-sample",
    "POST /api/dataset/capture-session/start",
    "GET /api/dataset/capture-session",
    "POST /api/dataset/capture-session/capture",
    "POST /api/dataset/capture-session/stop",
    "POST /api/dataset/manual-url",
    "POST /api/dataset/web-discovery/search",
    "POST /api/dataset/relabel",
    "POST /api/dataset/delete",
    "POST /api/dataset/bulk",
    "POST /api/dataset/quarantine",
    "GET /api/logs",
    "WEBSOCKET /ws/live",
}


@pytest.fixture(autouse=True)
def _isolated_agent_env(monkeypatch, tmp_path):
    for name in (
        "TRASH_SORTER_AGENT_TOKEN",
        "TRASH_SORTER_ADMIN_TOKEN",
        "TRASH_SORTER_USER_TOKEN",
        "TRASH_SORTER_AUTH_DB",
        "TRASH_SORTER_AUTH_DATABASE_URL",
        "DATABASE_URL",
        "TRASH_SORTER_AUTH_DEV_DEFAULTS",
        "TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME",
        "TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD",
        "TRASH_SORTER_SESSION_HOURS",
        "TRASH_SORTER_ALLOWED_ORIGINS",
        "OPENAI_API_KEY",
        "OPENAI_USER_ADVISOR_MODEL",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "DEEPSEEK_TIMEOUT_SECONDS",
        "GOOGLE_CSE_API_KEY",
        "GOOGLE_CSE_ID",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    api_module._login_limiter._failures.clear()


def _runtime(tmp_path: Path) -> AgentRuntime:
    cfg = AppConfig()
    cfg.device.device_id = "qa-device"
    cfg.device.device_name = "EcoSort QA Station"
    cfg.device.location = "QA Lab"
    cfg.device.owner_username = USER_USERNAME
    cfg.capture.output_dir = str(tmp_path / "dataset_v2")
    cfg_path = tmp_path / "config.json"
    save_config(cfg, cfg_path)
    return AgentRuntime(
        config_file=cfg_path,
        history_file=tmp_path / "history.db",
        dataset_file=tmp_path / "dataset.db",
    )


def _client(tmp_path: Path) -> tuple[TestClient, AgentRuntime]:
    runtime = _runtime(tmp_path)
    return TestClient(create_app(runtime=runtime)), runtime


def _image_bytes(width: int = 48, height: int = 36) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), (126, 172, 118)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _yolo_zip_bytes(label_name: str = "Paper") -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr(
            "data.yaml",
            f"train: train/images\nval: train/images\nnames:\n  0: {label_name}\n",
        )
        zf.writestr("train/images/sample.jpg", _image_bytes())
        zf.writestr("train/labels/sample.txt", "0 0.5 0.5 0.5 0.5\n")
    return buffer.getvalue()


def _seed_accounts() -> dict[str, dict[str, object]]:
    service = AuthService()
    service.create_account(ADMIN_USERNAME, ADMIN_PASSWORD, "admin")
    service.create_account(USER_USERNAME, USER_PASSWORD, "user")
    return {str(row["username"]): row for row in service.list_accounts()}


def _login(client: TestClient, username: str, password: str) -> dict[str, object]:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_history(
    runtime: AgentRuntime,
    tmp_path: Path,
    *,
    owner_account_id: int,
    owner_username: str,
) -> int:
    owned = tmp_path / "owned.jpg"
    owned_labeled = tmp_path / "owned-labeled.jpg"
    other = tmp_path / "other.jpg"
    legacy = tmp_path / "legacy.jpg"
    for image_path in (owned, owned_labeled, other, legacy):
        image_path.write_bytes(_image_bytes())
    service = HistoryService(runtime.history_file)
    try:
        owned_id = service.insert(
            track_id=11,
            ts=datetime.now(UTC) - timedelta(days=1),
            cls_id=1,
            cls_name="Paper",
            conf=0.91,
            bbox=(1, 2, 40, 30),
            image_path=str(owned),
            annotated_path=str(owned_labeled),
            route_label="Tái chế",
            bin_index=3,
            uart_command="I",
            owner_account_id=owner_account_id,
            owner_username=owner_username,
            device_id=runtime.cfg.device.device_id,
        )
        service.insert(
            track_id=12,
            ts=datetime.now(UTC) - timedelta(days=2),
            cls_id=2,
            cls_name="Food waste",
            conf=0.83,
            bbox=(1, 2, 40, 30),
            image_path=str(other),
            annotated_path=str(other),
            route_label="Hữu cơ",
            bin_index=1,
            uart_command="O",
            owner_account_id=owner_account_id + 100,
            owner_username="other-user",
            device_id=runtime.cfg.device.device_id,
        )
        service.insert(
            track_id=13,
            ts=datetime.now(UTC) - timedelta(days=3),
            cls_id=3,
            cls_name="Plastic bag",
            conf=0.74,
            bbox=(1, 2, 40, 30),
            image_path=str(legacy),
            annotated_path=str(legacy),
            route_label="Vô cơ",
            bin_index=2,
            uart_command="R",
        )
    finally:
        service.close()
    return owned_id


def _queue_dir(runtime: AgentRuntime) -> Path:
    return Path(runtime.cfg.capture.output_dir) / "low_conf_queue"


def _write_queue_item(
    runtime: AgentRuntime,
    stem: str,
    *,
    cls_name: str = "Paper",
    cls_id: int = 1,
    source: str = "manual_import",
    reviewed: bool = True,
    trusted: bool = True,
) -> Path:
    queue_dir = _queue_dir(runtime)
    queue_dir.mkdir(parents=True, exist_ok=True)
    image_path = queue_dir / f"{stem}.jpg"
    image_path.write_bytes(_image_bytes())
    meta = {
        "ts": "2026-06-09T08:00:00+00:00",
        "source": source if trusted else "untrusted",
        "reviewed": reviewed,
        "boxes": [{"cls_id": cls_id, "cls_name": cls_name, "conf": 1.0, "xyxy": [1, 1, 46, 34]}],
    }
    image_path.with_suffix(".json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )
    catalog = DatasetCatalog(runtime.dataset_file)
    try:
        catalog.upsert_item(image_path, meta)
    finally:
        catalog.close()
    return image_path


def _capture_state(active: bool, *, cls_name: str = "Paper", last_image_path: str = "") -> dict[str, object]:
    return {
        "active": active,
        "session_id": "qa-session" if active else "",
        "cls_name": cls_name if active else "",
        "cls_id": 1 if active else 0,
        "target_count": 8,
        "holdout_count": 2,
        "accepted_count": 1 if active else 0,
        "training_count": 1 if active else 0,
        "holdout_accepted": 0,
        "rejected_count": 0,
        "last_message": "QA capture state",
        "last_image_path": last_image_path,
    }


def _patch_safe_runtime(monkeypatch, runtime: AgentRuntime) -> None:
    monkeypatch.setattr(runtime, "model_classes", lambda: {1: "Paper", 2: "Food waste", 3: "Plastic bag"})
    monkeypatch.setattr(runtime, "start_camera", lambda: (True, "QA camera mock started"))
    monkeypatch.setattr(runtime, "stop_camera", lambda: (True, "QA camera mock stopped"))
    monkeypatch.setattr(runtime, "latest_jpeg", lambda: _image_bytes())
    monkeypatch.setattr(
        runtime,
        "capture_camera_sample",
        lambda cls_name, cls_id, use_latest_detection_box=True: _write_queue_item(
            runtime, "camera_sample", cls_name=cls_name, cls_id=cls_id, source="manual_camera_capture"
        ),
    )
    monkeypatch.setattr(
        runtime,
        "capture_unknown_learn_sample",
        lambda cls_name, cls_id: _write_queue_item(
            runtime,
            "unknown_capture",
            cls_name=cls_name,
            cls_id=cls_id,
            source="manual_camera_capture",
            reviewed=False,
        ),
    )
    monkeypatch.setattr(
        runtime,
        "start_capture_session",
        lambda cls_name, cls_id, target_count=24, holdout_count=6: _capture_state(True, cls_name=cls_name),
    )
    monkeypatch.setattr(runtime, "capture_session_status", lambda: _capture_state(True))
    monkeypatch.setattr(runtime, "capture_session_frame", lambda **kwargs: _capture_state(True))
    monkeypatch.setattr(runtime, "stop_capture_session", lambda: _capture_state(False))
    monkeypatch.setattr(
        api_module,
        "suggest_unknown_labels",
        lambda **kwargs: {"available": False, "provider": "local", "suggestions": []},
    )
    monkeypatch.setattr(api_module, "import_manual_image_urls", lambda *args, **kwargs: 1)


def _route_table(app) -> set[str]:
    routes: set[str] = set()
    for route in app.routes:
        if isinstance(route, APIRoute):
            if not (route.path_format.startswith("/api/") or route.path_format == "/api/health"):
                continue
            methods = sorted((route.methods or set()) - {"HEAD", "OPTIONS"})
            for method in methods:
                routes.add(f"{method} {route.path_format}")
        elif isinstance(route, WebSocketRoute) and route.path.startswith("/ws/"):
            routes.add(f"WEBSOCKET {route.path}")
    return routes


def test_fastapi_agent_route_table_is_fully_classified(tmp_path):
    client, runtime = _client(tmp_path)
    try:
        assert _route_table(client.app) == EXPECTED_AGENT_ROUTES
    finally:
        runtime.close()


def test_auth_user_rbac_and_scoped_user_api_contract(tmp_path):
    accounts = _seed_accounts()
    client, runtime = _client(tmp_path)
    try:
        user_account_id = int(accounts[USER_USERNAME]["id"])
        owned_id = _seed_history(
            runtime,
            tmp_path,
            owner_account_id=user_account_id,
            owner_username=USER_USERNAME,
        )
        admin = _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
        user = _login(client, USER_USERNAME, USER_PASSWORD)
        admin_headers = _headers(str(admin["token"]))
        user_headers = _headers(str(user["token"]))

        assert client.get("/api/health").json()["ok"] is True
        assert client.get("/api/me", headers=user_headers).json()["role"] == "user"
        assert client.get("/api/me", headers=admin_headers).json()["role"] == "admin"

        for path in (
            "/api/user/dashboard",
            "/api/user/analytics?range_days=30",
            "/api/user/device",
            "/api/user/report?range_days=30",
            "/api/user/experience?range_days=30",
            "/api/user/history?limit=20",
            "/api/user/history/export.csv?range_days=30",
        ):
            response = client.get(path, headers=user_headers)
            assert response.status_code == 200, f"{path}: {response.text}"

        user_history = client.get("/api/user/history?limit=20", headers=user_headers).json()
        assert user_history["total"] == 1
        assert user_history["rows"][0]["id"] == owned_id
        assert "image_path" not in user_history["rows"][0]

        image_response = client.get(f"/api/user/history/{owned_id}/image", headers=user_headers)
        assert image_response.status_code == 200
        assert image_response.headers["content-type"].startswith("image/")
        assert client.get(f"/api/user/history/{owned_id + 1}/image", headers=user_headers).status_code == 404

        advisor = client.post(
            "/api/user/advisor",
            headers=user_headers,
            json={"range_days": 30, "question": "Hôm qua tôi bỏ gì?"},
        )
        assert advisor.status_code == 200
        chat = client.post(
            "/api/user/chat",
            headers=user_headers,
            json={"message": "Tóm tắt rác tái chế của tôi"},
        )
        assert chat.status_code == 200
        chat_payload = chat.json()
        assert chat_payload["role"] == "user"
        assert chat_payload["profile"] == "trash_sorter_user"
        assert chat_payload["model"] == "deepseek-v4-flash"

        for path in (
            "/api/status",
            "/api/admin/accounts",
            "/api/history",
            "/api/dataset/summary",
            "/api/settings",
            "/api/model/classes",
            "/api/camera/stream",
        ):
            response = client.get(path, headers=user_headers, params={"token": str(user["token"])})
            assert response.status_code == 403, f"{path}: {response.status_code} {response.text}"

        logout = client.post("/api/auth/logout", headers=user_headers)
        assert logout.status_code == 200
        assert client.get("/api/me", headers=user_headers).status_code == 401
    finally:
        runtime.close()


def test_admin_accounts_knowledge_and_chat_contract(tmp_path):
    _seed_accounts()
    client, runtime = _client(tmp_path)
    try:
        admin = _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
        user = _login(client, USER_USERNAME, USER_PASSWORD)
        admin_headers = _headers(str(admin["token"]))
        user_headers = _headers(str(user["token"]))

        assert client.get("/api/admin/accounts", headers=admin_headers).status_code == 200
        created = client.post(
            "/api/admin/accounts",
            headers=admin_headers,
            json={"username": "qa-created-user", "password": "qa-created-pass-123", "role": "user"},
        )
        assert created.status_code == 200, created.text
        reset = client.post(
            "/api/admin/accounts/qa-created-user/reset-password",
            headers=admin_headers,
            json={"password": "qa-created-reset-123"},
        )
        assert reset.status_code == 200
        patched = client.patch(
            "/api/admin/accounts/qa-created-user",
            headers=admin_headers,
            json={"is_active": False},
        )
        assert patched.status_code == 200
        assert patched.json()["is_active"] is False

        backfill = client.post(
            "/api/admin/history/backfill-owner",
            headers=admin_headers,
            params={"owner_username": USER_USERNAME},
        )
        assert backfill.status_code == 200

        catalog = client.get("/api/admin/knowledge", headers=admin_headers)
        assert catalog.status_code == 200
        upsert = client.post(
            "/api/admin/knowledge",
            headers=admin_headers,
            json={
                "id": "qa-routing",
                "title": "QA routing",
                "roles": ["admin", "user"],
                "keywords": ["camera", "rác", "thùng"],
                "text": "Quy tắc QA: giấy đi thùng tái chế, thức ăn đi thùng hữu cơ.",
                "enabled": True,
            },
        )
        assert upsert.status_code == 200
        patch = client.patch(
            "/api/admin/knowledge/qa-routing",
            headers=admin_headers,
            json={"enabled": False},
        )
        assert patch.status_code == 200
        reload_response = client.post("/api/admin/knowledge/reload", headers=admin_headers)
        assert reload_response.status_code == 200
        evaluate = client.post(
            "/api/admin/knowledge/evaluate",
            headers=admin_headers,
            json={"role": "admin", "question": "Camera không nhận rác thì kiểm tra gì?"},
        )
        assert evaluate.status_code == 200
        assert evaluate.json()["snippets"]

        chat = client.post(
            "/api/admin/chat",
            headers=admin_headers,
            json={"message": "Kiểm tra camera và UART hôm nay"},
        )
        assert chat.status_code == 200
        payload = chat.json()
        assert payload["role"] == "admin"
        assert payload["profile"] == "trash_sorter_admin"
        assert payload["model"] == "deepseek-v4-flash"
        forbidden = client.post(
            "/api/admin/chat",
            headers=user_headers,
            json={"message": "Tôi có được xem admin không?"},
        )
        assert forbidden.status_code == 403

        for path in (
            "/api/admin/accounts",
            "/api/admin/knowledge",
        ):
            assert client.get(path, headers=user_headers).status_code == 403
    finally:
        runtime.close()


def test_admin_runtime_hardware_camera_websocket_and_settings_contract(tmp_path, monkeypatch):
    _seed_accounts()
    client, runtime = _client(tmp_path)
    _patch_safe_runtime(monkeypatch, runtime)
    try:
        admin = _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
        user = _login(client, USER_USERNAME, USER_PASSWORD)
        admin_headers = _headers(str(admin["token"]))

        assert client.get("/api/status", headers=admin_headers).status_code == 200
        assert client.get("/api/hardware/profile", headers=admin_headers).status_code == 200
        assert client.post("/api/hardware/test", headers=admin_headers, json={"command": "I"}).status_code == 200
        assert client.post("/api/hardware/audio-test", headers=admin_headers, json={"track": 1}).status_code == 200
        assert client.post(
            "/api/hardware/mp3-test",
            headers=admin_headers,
            json={"command": "STATUS", "value": None},
        ).status_code == 200
        assert client.post(
            "/api/hardware/servo-angle",
            headers=admin_headers,
            json={"d6": 90, "d7": 90, "label": "QA"},
        ).status_code == 200
        assert client.post(
            "/api/hardware/home-angle",
            headers=admin_headers,
            json={"d6": 90, "d7": 90, "label": "QA"},
        ).status_code == 200
        assert client.post(
            "/api/hardware/sort-angle",
            headers=admin_headers,
            json={"command": "I", "d6": 90, "d7": 90, "label": "QA"},
        ).status_code == 200
        assert client.get("/api/hardware/diagnostics", headers=admin_headers).status_code == 200
        assert client.post("/api/hardware/reconnect", headers=admin_headers).status_code == 200
        assert client.get("/api/actuation/test-mode", headers=admin_headers).status_code == 200
        assert client.put(
            "/api/actuation/test-mode",
            headers=admin_headers,
            json={"enabled": False},
        ).status_code == 200
        assert client.post("/api/devices/refresh", headers=admin_headers).status_code == 200
        assert client.post("/api/camera/start", headers=admin_headers).status_code == 200
        assert client.post("/api/camera/stop", headers=admin_headers).status_code == 200

        settings = client.get("/api/settings", headers=admin_headers)
        assert settings.status_code == 200
        settings_payload = settings.json()["config"]
        settings_payload["device"]["location"] = "QA Updated"
        assert client.put("/api/settings", headers=admin_headers, json=settings_payload).status_code == 200
        assert client.get("/api/mappings", headers=admin_headers).status_code == 200
        assert client.put(
            "/api/mappings",
            headers=admin_headers,
            json=[{"class_name": "Paper", "command": "I", "bin_index": 3, "enabled": True}],
        ).status_code == 200
        assert client.get("/api/model/classes", headers=admin_headers).json()["classes"]
        assert client.get("/api/common-waste/catalog", headers=admin_headers).json()["items"]

        with client.websocket_connect(f"/ws/live?token={admin['token']}") as websocket:
            payload = websocket.receive_json()
            assert "status" in payload
            assert "detections" in payload
        with pytest.raises(WebSocketDisconnect), client.websocket_connect(f"/ws/live?token={user['token']}"):
            pass
    finally:
        runtime.close()


def test_admin_history_training_dataset_and_logs_contract(tmp_path, monkeypatch):
    accounts = _seed_accounts()
    client, runtime = _client(tmp_path)
    _patch_safe_runtime(monkeypatch, runtime)
    try:
        admin = _login(client, ADMIN_USERNAME, ADMIN_PASSWORD)
        admin_headers = _headers(str(admin["token"]))
        owned_id = _seed_history(
            runtime,
            tmp_path,
            owner_account_id=int(accounts[USER_USERNAME]["id"]),
            owner_username=USER_USERNAME,
        )
        queue_image = _write_queue_item(runtime, "contract_item")
        delete_image = _write_queue_item(runtime, "delete_item")

        assert client.get("/api/training/status", headers=admin_headers).status_code == 200
        assert client.get("/api/learn-now/status?cls_name=Paper", headers=admin_headers).status_code == 200
        assert client.get("/api/dataset/source-quality", headers=admin_headers).status_code == 200
        assert client.post(
            "/api/learn-now/refresh-references?cls_name=Paper",
            headers=admin_headers,
        ).status_code == 200
        assert client.post(
            "/api/learn-now/unknown/capture",
            headers=admin_headers,
            json={"manual_hint": "giấy", "approved_cls_name": "Paper", "cls_id": 1},
        ).status_code == 200
        micro_train = client.post(
            "/api/learn-now/micro-train/start",
            headers=admin_headers,
            json={"cls_name": "Paper", "profile": "micro"},
        )
        assert micro_train.status_code == 409

        history = client.get("/api/history?limit=10", headers=admin_headers)
        assert history.status_code == 200
        assert history.json()["total"] >= 1
        assert client.get("/api/history/export.csv", headers=admin_headers).status_code == 200
        assert client.get(f"/api/history/{owned_id}/image", headers=admin_headers).status_code == 200

        assert client.get("/api/dataset/summary", headers=admin_headers).status_code == 200
        assert client.post("/api/dataset/sync", headers=admin_headers).status_code == 200
        items = client.get("/api/dataset/items?limit=20", headers=admin_headers)
        assert items.status_code == 200
        item_id = queue_image.stem
        assert client.get(f"/api/dataset/items/{item_id}", headers=admin_headers).status_code == 200
        assert client.get(f"/api/dataset/items/{item_id}/image", headers=admin_headers).status_code == 200
        boxes = {
            "boxes": [
                {"cls_id": 1, "cls_name": "Paper", "conf": 1.0, "xyxy": [2, 2, 42, 30]},
            ]
        }
        assert client.put(
            f"/api/dataset/items/{item_id}/boxes",
            headers=admin_headers,
            json=boxes,
        ).status_code == 200
        import_response = client.post(
            "/api/dataset/import",
            headers=admin_headers,
            data={"source_name": "qa-yolo"},
            files={"file": ("dataset.zip", _yolo_zip_bytes(), "application/zip")},
        )
        assert import_response.status_code == 200, import_response.text
        manual_response = client.post(
            "/api/dataset/manual",
            headers=admin_headers,
            data={"cls_name": "Paper", "cls_id": "1"},
            files=[("files", ("manual.jpg", _image_bytes(), "image/jpeg"))],
        )
        assert manual_response.status_code == 200
        assert client.post(
            "/api/dataset/camera-sample",
            headers=admin_headers,
            json={"cls_name": "Paper", "cls_id": 1, "use_latest_detection_box": False},
        ).status_code == 200
        assert client.post(
            "/api/dataset/capture-session/start",
            headers=admin_headers,
            json={"cls_name": "Paper", "cls_id": 1, "target_count": 8, "holdout_count": 2},
        ).status_code == 200
        assert client.get("/api/dataset/capture-session", headers=admin_headers).status_code == 200
        assert client.post(
            "/api/dataset/capture-session/capture",
            headers=admin_headers,
            json={"pose_index": 1, "use_latest_detection_box": False},
        ).status_code == 200
        assert client.post("/api/dataset/capture-session/stop", headers=admin_headers).status_code == 200
        manual_url = client.post(
            "/api/dataset/manual-url",
            headers=admin_headers,
            json={
                "urls": ["https://example.com/paper.jpg"],
                "cls_name": "Paper",
                "cls_id": 1,
                "source_page_url": "https://example.com/source",
                "source_license": "CC-BY-4.0",
                "source_author": "QA",
                "source_type": "licensed_url",
                "generated": False,
            },
        )
        assert manual_url.status_code == 200, manual_url.text
        assert client.post(
            "/api/dataset/web-discovery/search",
            headers=admin_headers,
            json={"cls_name": "Paper", "query": "paper waste", "limit": 1},
        ).status_code == 200
        assert client.post(
            "/api/dataset/relabel",
            headers=admin_headers,
            json={"image_paths": [str(queue_image)], "cls_name": "Paper", "cls_id": 1},
        ).status_code == 200
        assert client.post(
            "/api/dataset/bulk",
            headers=admin_headers,
            json={"action": "mark_untrusted", "image_paths": [str(queue_image)]},
        ).status_code == 200
        assert client.post("/api/dataset/quarantine", headers=admin_headers).status_code == 200
        assert client.post(
            "/api/dataset/delete",
            headers=admin_headers,
            json={"image_paths": [str(delete_image)]},
        ).status_code == 200
        logs = client.get("/api/logs?limit=50", headers=admin_headers)
        assert logs.status_code == 200
        assert "lines" in logs.json()
    finally:
        runtime.close()
