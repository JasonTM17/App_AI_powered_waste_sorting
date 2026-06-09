import hashlib
import json
import sqlite3
import zipfile
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from starlette.websockets import WebSocketDisconnect

from app.agent import runtime as runtime_module
from app.agent.api import _training_status, create_app
from app.agent.auth_service import AuthService
from app.agent.runtime import AgentRuntime
from app.core.config import AppConfig, save_config
from app.core.history import HistoryService


@pytest.fixture(autouse=True)
def _clear_agent_auth_env(monkeypatch, tmp_path):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.delenv("TRASH_SORTER_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("TRASH_SORTER_USER_TOKEN", raising=False)
    monkeypatch.delenv("TRASH_SORTER_AUTH_DB", raising=False)
    monkeypatch.delenv("TRASH_SORTER_AUTH_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TRASH_SORTER_AUTH_DEV_DEFAULTS", raising=False)
    monkeypatch.delenv("TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("TRASH_SORTER_SESSION_HOURS", raising=False)
    monkeypatch.delenv("TRASH_SORTER_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_USER_ADVISOR_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.delenv("DEEPSEEK_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))


def _runtime(tmp_path: Path) -> AgentRuntime:
    cfg = AppConfig()
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


def _image_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 24), (120, 140, 90)).save(buf, format="JPEG")
    return buf.getvalue()


def _yolo_zip_bytes(label_name: str = "Plastic bottle") -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "data.yaml",
            f"train: train/images\nval: train/images\nnames:\n  0: {label_name}\n",
        )
        zf.writestr("train/images/sample.jpg", _image_bytes())
        zf.writestr("train/labels/sample.txt", "0 0.5 0.5 0.5 0.5\n")
    return buf.getvalue()


def _make_queue_item(queue_dir: Path) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    img_path = queue_dir / "manual_abc.jpg"
    img_path.write_bytes(_image_bytes())
    meta = {
        "ts": "2026-05-22T08:00:00",
        "source": "manual_import",
        "boxes": [
            {
                "cls_id": 1,
                "cls_name": "Paper",
                "conf": 1.0,
                "xyxy": [0, 0, 32, 24],
            }
        ],
    }
    img_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def _make_auto_queue_item(queue_dir: Path, *, reviewed: bool) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    img_path = queue_dir / ("auto_reviewed.jpg" if reviewed else "auto_raw.jpg")
    img_path.write_bytes(_image_bytes())
    meta = {
        "ts": "2026-05-22T08:00:00",
        "source": "auto_low_conf",
        "reviewed": reviewed,
        "boxes": [
            {
                "cls_id": 1,
                "cls_name": "Paper",
                "conf": 0.6,
                "xyxy": [0, 0, 32, 24],
            }
        ],
    }
    img_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def _make_reviewed_learn_now_item(queue_dir: Path, name: str, cls_name: str) -> None:
    queue_dir.mkdir(parents=True, exist_ok=True)
    img_path = queue_dir / f"{name}.jpg"
    img_path.write_bytes(_image_bytes())
    meta = {
        "ts": "2026-05-22T08:00:00",
        "source": "manual_camera_capture",
        "reviewed": True,
        "boxes": [
            {
                "cls_id": 999,
                "cls_name": cls_name,
                "conf": 1.0,
                "xyxy": [1, 1, 30, 22],
            }
        ],
    }
    img_path.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")


def test_training_status_clamps_finished_resume_epoch(tmp_path, monkeypatch):
    previous = tmp_path / "runs" / "train" / "previous"
    current = tmp_path / "runs" / "train" / "current"
    previous.mkdir(parents=True)
    current.mkdir(parents=True)
    (previous / "results.csv").write_text(
        "epoch,time\n20,123\n",
        encoding="utf-8",
    )
    (current / "args.yaml").write_text(
        "epochs: 29\nmodel: runs/train/previous/weights/last.pt\n",
        encoding="utf-8",
    )
    (current / "results.csv").write_text(
        "epoch,time,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B)\n"
        "29,456,0.8,0.7,0.75,0.6\n",
        encoding="utf-8",
    )
    weights = current / "weights"
    weights.mkdir()
    (weights / "best.pt").write_bytes(b"model")
    monkeypatch.setattr("app.agent.api._training_processes", lambda: [])

    status = _training_status(tmp_path)

    assert status.segment_epoch == 29
    assert status.segment_epochs == 29
    assert status.completed_epoch == 50
    assert status.target_epoch == 50
    assert status.progress_percent == 100.0


def test_agent_health_and_status(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        assert client.get("/api/health").status_code == 200
        res = client.get("/api/status")
        assert res.status_code == 200
        status = res.json()
        assert status["camera"]["running"] is False
        assert status["three_bin_classifier"]["running"] is False
    finally:
        runtime.close()


def test_history_returns_labeled_image_fields_and_serves_image(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    image_path = tmp_path / "capture.jpg"
    labeled_path = tmp_path / "capture-labeled.jpg"
    image_path.write_bytes(_image_bytes())
    labeled_path.write_bytes(_image_bytes())
    service = HistoryService(runtime.history_file)
    try:
        row_id = service.insert(
            track_id=7,
            ts=datetime.now(UTC),
            cls_id=1,
            cls_name="Paper",
            conf=0.88,
            bbox=(1, 2, 20, 22),
            image_path=str(image_path),
            annotated_path=str(labeled_path),
            route_label="Vô cơ",
            bin_index=2,
            uart_command="R",
        )
    finally:
        service.close()
    try:
        res = client.get("/api/history?limit=1")
        assert res.status_code == 200
        row = res.json()["rows"][0]
        assert row["id"] == row_id
        assert row["annotated_path"] == str(labeled_path)
        assert row["route_label"] == "Vô cơ"
        img_res = client.get(f"/api/history/{row_id}/image")
        assert img_res.status_code == 200
        assert img_res.content
    finally:
        runtime.close()


def test_status_lists_only_external_usb_cameras(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.setattr(
        "app.agent.runtime.list_pnp_cameras",
        lambda: [
            {"name": "Integrated Webcam", "instance_id": "USB\\BUILTIN", "is_usb": True, "is_external": False},
            {"name": "USB Camera", "instance_id": "USB\\EXTERNAL", "is_usb": True, "is_external": True},
        ],
    )
    client, runtime = _client(tmp_path)
    try:
        status = client.get("/api/status").json()
        assert status["usb_cameras"] == [
            {"name": "USB Camera", "instance_id": "USB\\EXTERNAL", "is_usb": True, "is_external": True}
        ]
    finally:
        runtime.close()


def test_live_payload_reuses_device_scan_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    calls = {"camera": 0, "serial": 0}

    def cameras():
        calls["camera"] += 1
        return [{"name": "USB Camera", "instance_id": "USB\\EXTERNAL", "is_usb": True, "is_external": True}]

    def serial_ports():
        calls["serial"] += 1
        return [{"device": "COM9", "name": "Arduino", "hwid": "USB\\VID", "is_usb": True}]

    monkeypatch.setattr("app.agent.runtime.list_pnp_cameras", cameras)
    monkeypatch.setattr("app.agent.runtime.list_serial_ports", serial_ports)
    runtime = _runtime(tmp_path)
    calls["camera"] = 0
    calls["serial"] = 0
    try:
        runtime.live_payload()
        runtime.live_payload()
        runtime.status()
        assert calls == {"camera": 1, "serial": 1}
    finally:
        runtime.close()


def test_devices_refresh_clears_device_scan_cache(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    state = {"name": "USB Camera A"}

    def cameras():
        return [{"name": state["name"], "instance_id": "USB\\EXTERNAL", "is_usb": True, "is_external": True}]

    monkeypatch.setattr("app.agent.runtime.list_pnp_cameras", cameras)
    monkeypatch.setattr("app.agent.runtime.list_serial_ports", lambda: [])
    client, runtime = _client(tmp_path)
    try:
        assert client.get("/api/status").json()["usb_cameras"][0]["name"] == "USB Camera A"
        state["name"] = "USB Camera B"
        assert client.get("/api/status").json()["usb_cameras"][0]["name"] == "USB Camera A"
        refreshed = client.post("/api/devices/refresh").json()
        assert refreshed["usb_cameras"][0]["name"] == "USB Camera B"
    finally:
        runtime.close()


def test_agent_requires_token_when_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AGENT_TOKEN", "secret")
    client, runtime = _client(tmp_path)
    try:
        assert client.get("/api/status").status_code == 401
        res = client.get("/api/status", headers={"Authorization": "Bearer secret"})
        assert res.status_code == 200
    finally:
        runtime.close()


def test_auth_dev_default_accounts_login_logout_and_gate_roles(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("TRASH_SORTER_AUTH_DEV_DEFAULTS", "1")
    client, runtime = _client(tmp_path)
    try:
        assert client.get("/api/me").status_code == 401
        wrong = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
        assert wrong.status_code == 401

        admin_login = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        assert admin_login.status_code == 200
        admin_body = admin_login.json()
        assert admin_body["role"] == "admin"
        assert admin_body["username"] == "admin"
        assert admin_body["password_default"] is True
        assert "password_hash" not in json.dumps(admin_body)
        admin_token = admin_body["token"]
        blocked = client.get("/api/status", headers={"Authorization": f"Bearer {admin_token}"})
        assert blocked.status_code == 403
        assert "Password change required" in blocked.text
        changed = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"current_password": "admin123", "new_password": "admin-pass-123"},
        )
        assert changed.status_code == 200
        assert changed.json()["password_default"] is False
        assert client.get("/api/status", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200

        user_login = client.post("/api/auth/login", json={"username": "user", "password": "user123"})
        assert user_login.status_code == 200
        user_token = user_login.json()["token"]
        assert client.get(
            "/api/user/analytics?range_days=30",
            headers={"Authorization": f"Bearer {user_token}"},
        ).status_code == 403
        changed_user = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"current_password": "user123", "new_password": "user-pass-123"},
        )
        assert changed_user.status_code == 200
        assert client.get(
            "/api/user/analytics?range_days=30",
            headers={"Authorization": f"Bearer {user_token}"},
        ).status_code == 200
        assert client.get(
            "/api/status",
            headers={"Authorization": f"Bearer {user_token}"},
        ).status_code == 403
        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(
            f"/ws/live?token={user_token}"
        ):
            pass
        assert exc_info.value.code == 1008

        logout = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {admin_token}"})
        assert logout.status_code == 200
        assert client.get(
            "/api/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code == 401
    finally:
        runtime.close()


def test_auth_production_does_not_seed_default_passwords_without_env(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    client, runtime = _client(tmp_path)
    try:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert login.status_code == 503
        assert client.get("/api/status").status_code == 200
    finally:
        runtime.close()


def test_auth_bootstrap_admin_env_creates_admin_account(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("TRASH_SORTER_BOOTSTRAP_ADMIN_USERNAME", "owner")
    monkeypatch.setenv("TRASH_SORTER_BOOTSTRAP_ADMIN_PASSWORD", "owner-pass-123")
    client, runtime = _client(tmp_path)
    try:
        login = client.post(
            "/api/auth/login",
            json={"username": "owner", "password": "owner-pass-123"},
        )
        assert login.status_code == 200
        token = login.json()["token"]
        assert login.json()["password_default"] is False
        assert client.get("/api/status", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    finally:
        runtime.close()


def test_auth_inactive_account_is_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("TRASH_SORTER_AUTH_DEV_DEFAULTS", "1")
    AuthService().set_active("user", False)
    client, runtime = _client(tmp_path)
    try:
        login = client.post("/api/auth/login", json={"username": "user", "password": "user123"})
        assert login.status_code == 403
    finally:
        runtime.close()


def test_auth_expired_session_is_rejected(tmp_path, monkeypatch):
    auth_db = tmp_path / "auth.db"
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(auth_db))
    monkeypatch.setenv("TRASH_SORTER_AUTH_DEV_DEFAULTS", "1")
    client, runtime = _client(tmp_path)
    try:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        assert login.status_code == 200
        token = login.json()["token"]
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with sqlite3.connect(auth_db) as conn:
            conn.execute(
                "UPDATE sessions SET expires_at = ? WHERE token_hash = ?",
                ("2000-01-01T00:00:00+00:00", token_hash),
            )
        assert client.get("/api/status", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    finally:
        runtime.close()


def test_admin_account_management_resets_and_disables_accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    AuthService().create_account("admin", "admin-pass-123", "admin")
    client, runtime = _client(tmp_path)
    try:
        login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass-123"})
        admin_token = login.json()["token"]
        headers = {"Authorization": f"Bearer {admin_token}"}

        created = client.post(
            "/api/admin/accounts",
            headers=headers,
            json={"username": "worker", "password": "worker-pass-123", "role": "user"},
        )
        assert created.status_code == 200
        assert created.json()["password_default"] is True

        worker_login = client.post("/api/auth/login", json={"username": "worker", "password": "worker-pass-123"})
        assert worker_login.status_code == 200
        worker_token = worker_login.json()["token"]

        reset = client.post(
            "/api/admin/accounts/worker/reset-password",
            headers=headers,
            json={"password": "worker-reset-123"},
        )
        assert reset.status_code == 200
        assert reset.json()["password_default"] is True
        assert client.get("/api/me", headers={"Authorization": f"Bearer {worker_token}"}).status_code == 401

        patched = client.patch("/api/admin/accounts/worker", headers=headers, json={"is_active": False})
        assert patched.status_code == 200
        assert patched.json()["is_active"] is False
        disabled_login = client.post(
            "/api/auth/login",
            json={"username": "worker", "password": "worker-reset-123"},
        )
        assert disabled_login.status_code == 403
    finally:
        runtime.close()


def test_agent_role_tokens_gate_admin_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("TRASH_SORTER_USER_TOKEN", "user-secret")
    monkeypatch.setenv("TRASH_SORTER_AGENT_TOKEN", "legacy-secret")
    client, runtime = _client(tmp_path)
    try:
        assert client.get("/api/me").status_code == 401

        user_me = client.get("/api/me", headers={"Authorization": "Bearer user-secret"})
        assert user_me.status_code == 200
        assert user_me.json()["role"] == "user"
        assert client.get("/api/status", headers={"Authorization": "Bearer user-secret"}).status_code == 403
        assert client.get(
            "/api/hardware/profile",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.get(
            "/api/hardware/diagnostics",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.post(
            "/api/hardware/reconnect",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.post(
            "/api/hardware/servo-angle",
            json={"d6": 90, "d7": 100, "label": "Wait"},
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.post(
            "/api/hardware/home-angle",
            json={"d6": 90, "d7": 85, "label": "Home current"},
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.post(
            "/api/hardware/sort-angle",
            json={"command": "I", "d6": 0, "d7": 180, "label": "Tai che D6 min"},
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.get(
            "/api/actuation/test-mode",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.get(
            "/api/user/dashboard",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 200
        assert client.get(
            "/api/user/analytics?range_days=30",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 200
        assert client.get(
            "/api/user/device",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 200
        assert client.get(
            "/api/user/report?range_days=30",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 200
        assert client.get(
            "/api/user/experience?range_days=30",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 200
        assert client.get(
            "/api/user/history/export.csv?range_days=30",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 200
        assert client.post(
            "/api/user/advisor",
            json={"range_days": 30, "question": "Tu van giup toi"},
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 200
        assert client.get(
            "/api/history",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.get(
            "/api/history/export.csv",
            headers={"Authorization": "Bearer user-secret"},
        ).status_code == 403
        assert client.get("/api/camera/stream?token=user-secret").status_code == 403
        with pytest.raises(WebSocketDisconnect) as exc_info, client.websocket_connect(
            "/ws/live?token=user-secret"
        ):
            pass
        assert exc_info.value.code == 1008

        admin_status = client.get("/api/status", headers={"Authorization": "Bearer admin-secret"})
        assert admin_status.status_code == 200
        legacy_status = client.get("/api/status?token=legacy-secret")
        assert legacy_status.status_code == 200
    finally:
        runtime.close()


def test_hardware_profile_api_returns_selected_mapping(tmp_path):
    client, runtime = _client(tmp_path)
    try:
        body = client.get("/api/hardware/profile").json()
        assert body["profile_id"] == "LEGACY_2_SERVO_OPENSMART"
        assert body["audio_protocol"] == "open_smart_serial_mp3_a"
        assert body["baud"] == 9600
        assert body["gd5800"]["module"] == "OPEN-SMART Serial MP3 Player A"
        assert body["gd5800"]["serial_mode"] == "REVERSE_RX_D4_TX_D5"
        assert body["gd5800"]["tx_pin"] == "D5"
        assert body["gd5800"]["rx_pin"] == "D4"
        assert body["gd5800"]["multi_object_warning_track"] == 8
        assert body["calibration"]["home_candidates"][0] == {
            "label": "Home current",
            "D6": 90,
            "D7": 85,
        }
        assert body["calibration"]["inorganic_replay_candidates"][2] == {
            "label": "Vo co max max",
            "command": "R",
            "D6": 180,
            "D7": 180,
        }
        assert body["routes"][0] == {
            "command": "O",
            "label": "Huu co",
            "serial_payload": "huuco",
            "payload_line": "huuco\\n",
            "bin_index": 1,
            "servo_pin": "D6/D7",
            "servo_positions": {"D6": 90, "D7": 180},
            "gd5800_track": 2,
        }
        assert body["proximity_sensors"][0] == {
            "command": "O",
            "label": "Huu co",
            "pin": "D10",
            "active_level": 0,
            "gd5800_track": 5,
            "action": "audio_only",
            "controls_servo": False,
        }
    finally:
        runtime.close()


def test_hardware_test_api_is_admin_only_and_uses_runtime_uart(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("TRASH_SORTER_USER_TOKEN", "user-secret")
    client, runtime = _client(tmp_path)

    class FakeUart:
        connected = True

        def __init__(self):
            self.commands: list[str] = []

        def send_test(self, command: str):
            self.commands.append(command)
            return {
                "ok": True,
                "command": command,
                "payload": "voco\n",
                "port": "COM8",
                "ack_status": "ok",
                "elapsed_ms": 12,
                "message": "ACK:R from COM8",
            }

        def close(self):
            return None

    fake = FakeUart()
    runtime.cfg.uart.port = "COM8"
    runtime._uart = fake  # type: ignore[assignment]
    try:
        user_res = client.post(
            "/api/hardware/test",
            json={"command": "R"},
            headers={"Authorization": "Bearer user-secret"},
        )
        assert user_res.status_code == 403
        admin_res = client.post(
            "/api/hardware/test",
            json={"command": "R"},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert admin_res.status_code == 200
        assert admin_res.json() == {
            "ok": True,
            "command": "R",
            "payload": "voco\n",
            "port": "COM8",
            "ack_status": "ok",
            "elapsed_ms": 12,
            "message": "ACK:R from COM8",
        }
        assert fake.commands == ["R"]
    finally:
        runtime.close()


def test_hardware_audio_test_api_is_admin_only_and_uses_runtime_uart(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("TRASH_SORTER_USER_TOKEN", "user-secret")
    client, runtime = _client(tmp_path)

    class FakeUart:
        connected = True

        def __init__(self):
            self.tracks: list[int] = []

        def send_audio_test(self, track: int):
            self.tracks.append(track)
            return {
                "ok": True,
                "track": track,
                "payload": "AUDIO:5\n",
                "port": "COM8",
                "ack_status": "ok",
                "elapsed_ms": 8,
                "message": "ACK:AUDIO:5 from COM8",
            }

        def close(self):
            return None

    fake = FakeUart()
    runtime.cfg.uart.port = "COM8"
    runtime._uart = fake  # type: ignore[assignment]
    try:
        user_res = client.post(
            "/api/hardware/audio-test",
            json={"track": 5},
            headers={"Authorization": "Bearer user-secret"},
        )
        assert user_res.status_code == 403
        admin_res = client.post(
            "/api/hardware/audio-test",
            json={"track": 5},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert admin_res.status_code == 200
        assert admin_res.json() == {
            "ok": True,
            "track": 5,
            "payload": "AUDIO:5\n",
            "port": "COM8",
            "ack_status": "ok",
            "elapsed_ms": 8,
            "message": "ACK:AUDIO:5 from COM8",
        }
        assert fake.tracks == [5]
    finally:
        runtime.close()


def test_hardware_mp3_test_api_is_admin_only_and_uses_runtime_uart(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("TRASH_SORTER_USER_TOKEN", "user-secret")
    client, runtime = _client(tmp_path)

    class FakeUart:
        connected = True

        def __init__(self):
            self.commands: list[tuple[str, int | None]] = []

        def send_mp3_test(self, command: str, value: int | None = None):
            self.commands.append((command, value))
            return {
                "ok": True,
                "command": command,
                "value": value,
                "payload": "MP3:VOL:30\n",
                "port": "COM8",
                "ack_status": "ok",
                "elapsed_ms": 9,
                "message": "ACK:MP3:VOL:30 from COM8",
            }

        def close(self):
            return None

    fake = FakeUart()
    runtime.cfg.uart.port = "COM8"
    runtime._uart = fake  # type: ignore[assignment]
    try:
        user_res = client.post(
            "/api/hardware/mp3-test",
            json={"command": "VOL", "value": 30},
            headers={"Authorization": "Bearer user-secret"},
        )
        assert user_res.status_code == 403
        admin_res = client.post(
            "/api/hardware/mp3-test",
            json={"command": "VOL", "value": 30},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert admin_res.status_code == 200
        assert admin_res.json() == {
            "ok": True,
            "command": "VOL",
            "value": 30,
            "payload": "MP3:VOL:30\n",
            "port": "COM8",
            "ack_status": "ok",
            "elapsed_ms": 9,
            "message": "ACK:MP3:VOL:30 from COM8",
        }
        assert fake.commands == [("VOL", 30)]
    finally:
        runtime.close()


def test_servo_angle_test_api_is_admin_only_and_uses_runtime_uart(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("TRASH_SORTER_USER_TOKEN", "user-secret")
    client, runtime = _client(tmp_path)

    class FakeUart:
        connected = True

        def __init__(self):
            self.angles: list[tuple[int, int, str]] = []

        def send_angle_test(self, d6: int, d7: int, label: str = ""):
            self.angles.append((d6, d7, label))
            return {
                "ok": True,
                "command": "ANGLE",
                "route_command": None,
                "payload": "ANGLE:90:90\n",
                "port": "COM8",
                "ack_status": "ok",
                "elapsed_ms": 1910,
                "message": "ACK:ANGLE:90:90 from COM8",
                "d6": d6,
                "d7": d7,
                "label": label,
            }

        def send_home_test(self, d6: int, d7: int, label: str = ""):
            return {
                "ok": True,
                "command": "HOME",
                "route_command": None,
                "payload": f"HOME:{d6}:{d7}\n",
                "port": "COM8",
                "ack_status": "ok",
                "elapsed_ms": 180,
                "message": f"ACK:HOME:{d6}:{d7} from COM8",
                "d6": d6,
                "d7": d7,
                "label": label,
            }

        def send_sort_angle_test(self, command: str, d6: int, d7: int, label: str = ""):
            return {
                "ok": True,
                "command": "SORTTEST",
                "route_command": command,
                "payload": f"SORTTEST:{command}:{d6}:{d7}\n",
                "port": "COM8",
                "ack_status": "ok",
                "elapsed_ms": 2300,
                "message": f"ACK:SORTTEST:{command}:{d6}:{d7} from COM8",
                "d6": d6,
                "d7": d7,
                "label": label,
            }

        def close(self):
            return None

    fake = FakeUart()
    runtime.cfg.uart.port = "COM8"
    runtime._uart = fake  # type: ignore[assignment]
    try:
        user_res = client.post(
            "/api/hardware/servo-angle",
            json={"d6": 90, "d7": 90, "label": "Wait"},
            headers={"Authorization": "Bearer user-secret"},
        )
        assert user_res.status_code == 403
        admin_res = client.post(
            "/api/hardware/servo-angle",
            json={"d6": 90, "d7": 90, "label": "Wait"},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert admin_res.status_code == 200
        assert admin_res.json() == {
            "ok": True,
            "command": "ANGLE",
            "route_command": None,
            "payload": "ANGLE:90:90\n",
            "port": "COM8",
            "ack_status": "ok",
            "elapsed_ms": 1910,
            "message": "ACK:ANGLE:90:90 from COM8",
            "d6": 90,
            "d7": 90,
            "label": "Wait",
        }
        home_res = client.post(
            "/api/hardware/home-angle",
            json={"d6": 90, "d7": 85, "label": "Home current"},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert home_res.status_code == 200
        assert home_res.json()["payload"] == "HOME:90:85\n"
        user_sort_res = client.post(
            "/api/hardware/sort-angle",
            json={"command": "I", "d6": 0, "d7": 180, "label": "Tai che D6 min"},
            headers={"Authorization": "Bearer user-secret"},
        )
        assert user_sort_res.status_code == 403
        sort_res = client.post(
            "/api/hardware/sort-angle",
            json={"command": "I", "d6": 0, "d7": 180, "label": "Tai che D6 min"},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert sort_res.status_code == 200
        assert sort_res.json()["payload"] == "SORTTEST:I:0:180\n"
        assert sort_res.json()["route_command"] == "I"
        assert fake.angles == [(90, 90, "Wait")]
    finally:
        runtime.close()


def test_hardware_diagnostics_api_returns_uart_state(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-secret")
    client, runtime = _client(tmp_path)

    class FakeUart:
        connected = True
        message = "connected COM8 (plain_group); LEGACY_2_SERVO_OPENSMART"
        last_profile = "LEGACY_2_SERVO_OPENSMART"
        last_profile_at = 100.0
        last_pong_at = 101.0
        last_log = "firmware ready LEGACY_2_SERVO_OPENSMART"
        disconnect_reason = ""

        def __init__(self):
            self.last_ack = {"kind": "ack", "command": "R", "at": 102.0}
            self.last_proximity = {"command": "O", "at": 103.0}
            self.last_audio = {"command": "O", "track": 5, "source": "prox", "at": 104.0}
            self.last_mp3 = {"event": "tx", "detail": "7E 04 41 00 05 EF", "at": 104.5}
            self.last_mp3_tx = {"event": "tx", "detail": "7E 04 41 00 05 EF", "at": 104.5}
            self.last_mp3_rx = {"event": "rx", "detail": "7E 02 00 EF", "at": 104.7}

        def close(self):
            return None

    runtime.cfg.uart.port = "COM8"
    runtime._uart = FakeUart()  # type: ignore[assignment]
    monkeypatch.setattr("app.agent.runtime.time.time", lambda: 105.0)
    try:
        res = client.get(
            "/api/hardware/diagnostics",
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["selected_port"] == "COM8"
        assert body["uart_connected"] is True
        assert body["firmware_profile"] == "LEGACY_2_SERVO_OPENSMART"
        assert body["firmware_profile_age_s"] == 5.0
        assert body["last_pong_age_s"] == 4.0
        assert body["last_ack"]["command"] == "R"
        assert body["last_proximity"]["command"] == "O"
        assert body["last_audio"]["track"] == 5
        assert body["last_audio"]["source"] == "prox"
        assert body["last_mp3"]["event"] == "tx"
        assert body["last_mp3_tx"]["detail"] == "7E 04 41 00 05 EF"
        assert body["last_mp3_rx"]["detail"] == "7E 02 00 EF"
        assert body["audio_protocol"] == "open_smart_serial_mp3_a"
        assert body["warning"] == ""
    finally:
        runtime.close()


def test_actuation_test_mode_api_is_admin_only_and_returns_recent_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-secret")
    monkeypatch.setenv("TRASH_SORTER_USER_TOKEN", "user-secret")
    client, runtime = _client(tmp_path)
    service = HistoryService(runtime.history_file)
    try:
        service.insert(
            track_id=1,
            ts=datetime.now(UTC),
            cls_id=34,
            cls_name="Organic",
            conf=0.92,
            bbox=(1, 2, 20, 22),
            route_label="Huu co",
            bin_index=1,
            uart_command="O",
            ack_status="ok",
            rtt_ms=18,
        )
    finally:
        service.close()
    try:
        user_get = client.get(
            "/api/actuation/test-mode",
            headers={"Authorization": "Bearer user-secret"},
        )
        assert user_get.status_code == 403

        enabled = client.put(
            "/api/actuation/test-mode",
            json={"enabled": True},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert enabled.status_code == 200
        body = enabled.json()
        assert body["enabled"] is True
        assert body["uart_connected"] is False
        assert body["warning"] == "UART OFF, khong gui xuong phan cung"
        assert body["evidence"][0] == {
            "history_id": 1,
            "timestamp": body["evidence"][0]["timestamp"],
            "detected_class": "Organic",
            "confidence": 0.92,
            "route_label": "Huu co",
            "bin_index": 1,
            "command": "O",
            "serial_payload": "huuco\\n",
            "uart_sent": True,
            "ack_status": "ok",
            "rtt_ms": 18,
        }

        disabled = client.put(
            "/api/actuation/test-mode",
            json={"enabled": False},
            headers={"Authorization": "Bearer admin-secret"},
        )
        assert disabled.status_code == 200
        assert disabled.json()["enabled"] is False
    finally:
        runtime.close()


def test_runtime_autoselects_single_usb_uart_port(tmp_path, monkeypatch):
    monkeypatch.setattr(
        runtime_module,
        "list_serial_ports",
        lambda: [
            {"device": "COM3", "name": "Bluetooth", "hwid": "BTHENUM", "is_usb": False},
            {"device": "COM8", "name": "USB-SERIAL CH340", "hwid": "USB VID:1A86", "is_usb": True},
        ],
    )

    class FakeSender:
        connected = True
        message = "connected COM8 (plain_group)"

        def __init__(self, port, *args, **kwargs):
            self.port = port

        def open(self):
            return True

        def close(self):
            return None

    monkeypatch.setattr(runtime_module, "ThreadUartSender", FakeSender)
    runtime = _runtime(tmp_path)
    try:
        assert runtime.cfg.uart.port == "COM8"
        saved = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
        assert saved["uart"]["port"] == "COM8"
        assert runtime.status(include_devices=False).current_port == "COM8"
    finally:
        runtime.close()


def test_user_dashboard_returns_bins_waste_and_wellness_insights(tmp_path):
    client, runtime = _client(tmp_path)
    runtime.update_bin_fullness(2, 75)
    service = HistoryService(runtime.history_file)
    try:
        names = ["Plastic bottle"] * 4 + ["Disposable tableware"] * 4
        for index, cls_name in enumerate(names, start=1):
            service.insert(
                track_id=index,
                ts=datetime.now(UTC),
                cls_id=index,
                cls_name=cls_name,
                conf=0.9,
                bbox=(1, 2, 20, 22),
            )
    finally:
        service.close()

    original_monotonic = runtime_module.time.monotonic
    try:
        body = client.get("/api/user/dashboard").json()
        bin_two = next(item for item in body["bins"] if item["bin_index"] == 2)
        assert bin_two["percent"] == 75
        assert bin_two["stale"] is False
        assert body["sample_size"] == 8
        assert {item["kind"] for item in body["insights"]} == {"hydration", "fast_food"}
        assert "image_path" not in body["recent_waste"][0]

        runtime_module.time.monotonic = lambda: original_monotonic() + 11
        stale = client.get("/api/user/dashboard").json()
        stale_bin_two = next(item for item in stale["bins"] if item["bin_index"] == 2)
        assert stale_bin_two["stale"] is True
    finally:
        runtime_module.time.monotonic = original_monotonic
        runtime.close()


def test_user_analytics_returns_range_chart_data_and_keeps_payload_safe(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client, runtime = _client(tmp_path)
    runtime.update_bin_fullness(3, 42)
    now = datetime.now(UTC)
    service = HistoryService(runtime.history_file)
    try:
        rows = [
            (now, "Plastic bottle"),
            (now - timedelta(days=1), "Disposable tableware"),
            (now - timedelta(days=1), "Disposable tableware"),
            (now - timedelta(days=10), "Organic"),
            (now - timedelta(days=40), "Aluminum can"),
            (now - timedelta(days=100), "Paper"),
        ]
        for index, (ts, cls_name) in enumerate(rows, start=1):
            service.insert(
                track_id=index,
                ts=ts,
                cls_id=index,
                cls_name=cls_name,
                conf=0.9,
                bbox=(1, 2, 20, 22),
                image_path=f"C:/private/{index}.jpg",
                annotated_path=f"C:/private/{index}-labeled.jpg",
                meta_path=f"C:/private/{index}.json",
            )
    finally:
        service.close()

    try:
        body = client.get("/api/user/analytics?range_days=7").json()

        assert body["range_days"] == 7
        assert body["total"] == 3
        assert body["comparison"]["previous_total"] == 1
        assert body["comparison"]["delta"] == 2
        assert len(body["daily"]) == 7
        assert body["yesterday"]["total"] == 2
        top = body["top_classes"][0]
        assert top["cls_name"] == "Disposable tableware"
        assert top["count"] == 2
        route_counts = {item["command"]: item["count"] for item in body["route_totals"]}
        assert route_counts == {"O": 0, "R": 2, "I": 1}
        bin_three = next(item for item in body["bins"] if item["bin_index"] == 3)
        assert bin_three["percent"] == 42
        assert body["advisor_available"] is False
        assert "image_path" not in json.dumps(body)
        assert "private" not in json.dumps(body)

        long_body = client.get("/api/user/analytics?range_days=180").json()
        assert long_body["total"] == 6
        assert len(long_body["monthly"]) >= 4
    finally:
        runtime.close()


def test_user_history_and_analytics_are_scoped_to_account_owner(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    auth_service = AuthService()
    auth_service.create_account("alice", "alice-pass-123", "user")
    auth_service.create_account("bob", "bob-pass-123", "user")
    accounts = {row["username"]: row for row in auth_service.list_accounts()}
    client, runtime = _client(tmp_path)
    alice_image = tmp_path / "alice.jpg"
    bob_image = tmp_path / "bob.jpg"
    alice_image.write_bytes(_image_bytes())
    bob_image.write_bytes(_image_bytes())
    service = HistoryService(runtime.history_file)
    try:
        alice_id = service.insert(
            track_id=1,
            ts=datetime.now(UTC),
            cls_id=1,
            cls_name="Plastic bottle",
            conf=0.91,
            bbox=(1, 2, 20, 22),
            image_path=str(alice_image),
            owner_account_id=int(accounts["alice"]["id"]),
            owner_username="alice",
            device_id="device-a",
        )
        bob_id = service.insert(
            track_id=2,
            ts=datetime.now(UTC),
            cls_id=2,
            cls_name="Organic",
            conf=0.82,
            bbox=(1, 2, 20, 22),
            image_path=str(bob_image),
            owner_account_id=int(accounts["bob"]["id"]),
            owner_username="bob",
            device_id="device-a",
        )
        service.insert(
            track_id=3,
            ts=datetime.now(UTC),
            cls_id=3,
            cls_name="Paper",
            conf=0.77,
            bbox=(1, 2, 20, 22),
            image_path="C:/legacy/secret.jpg",
        )
    finally:
        service.close()

    try:
        login = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pass-123"})
        token = login.json()["token"]
        headers = {"Authorization": f"Bearer {token}"}

        analytics = client.get("/api/user/analytics?range_days=30", headers=headers)
        assert analytics.status_code == 200
        body = analytics.json()
        assert body["total"] == 1
        assert body["top_classes"][0]["cls_name"] == "Plastic bottle"
        assert "legacy" not in json.dumps(body)

        history = client.get("/api/user/history?limit=20", headers=headers)
        assert history.status_code == 200
        history_body = history.json()
        assert [row["id"] for row in history_body["rows"]] == [alice_id]
        assert "image_path" not in json.dumps(history_body)

        assert client.get(f"/api/user/history/{alice_id}/image?token={token}").status_code == 200
        assert client.get(f"/api/user/history/{bob_id}/image?token={token}").status_code == 404

        device = client.get("/api/user/device", headers=headers)
        assert device.status_code == 200
        assert [row["id"] for row in device.json()["recent_activity"]] == [alice_id]

        report = client.get("/api/user/report?range_days=30", headers=headers)
        assert report.status_code == 200
        report_body = report.json()
        assert report_body["analytics"]["total"] == 1
        assert "image_path" not in json.dumps(report_body)
        assert "legacy" not in json.dumps(report_body)
        assert report_body["csv_safe_fields"] == [
            "id",
            "ts",
            "cls_name",
            "confidence",
            "category",
            "route_label",
            "bin_index",
            "ack_status",
            "device_id",
        ]

        experience = client.get("/api/user/experience?range_days=30", headers=headers)
        assert experience.status_code == 200
        experience_body = experience.json()
        assert experience_body["range_days"] == 30
        assert experience_body["leaderboard"]
        assert "bob" not in json.dumps(experience_body).lower()
        assert "legacy" not in json.dumps(experience_body).lower()

        export = client.get("/api/user/history/export.csv?range_days=30", headers=headers)
        assert export.status_code == 200
        csv_text = export.text
        assert "Plastic bottle" in csv_text
        assert "Organic" not in csv_text
        assert "legacy" not in csv_text
        assert "image_path" not in csv_text
        assert "private" not in csv_text
        assert str(alice_image) not in csv_text
    finally:
        runtime.close()


def test_admin_knowledge_crud_evaluate_and_user_forbidden(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    AuthService().create_account("admin", "admin-pass-123", "admin")
    AuthService().create_account("viewer", "viewer-pass-123", "user")
    client, runtime = _client(tmp_path)
    try:
        admin_token = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-pass-123"},
        ).json()["token"]
        user_token = client.post(
            "/api/auth/login",
            json={"username": "viewer", "password": "viewer-pass-123"},
        ).json()["token"]

        blocked = client.get("/api/admin/knowledge", headers={"Authorization": f"Bearer {user_token}"})
        assert blocked.status_code == 403

        catalog = client.get("/api/admin/knowledge", headers={"Authorization": f"Bearer {admin_token}"})
        assert catalog.status_code == 200
        assert catalog.json()["total"] >= 10
        assert any(item["id"] == "taxonomy-three-bins" for item in catalog.json()["entries"])

        created = client.post(
            "/api/admin/knowledge",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Quy trình kiểm tra camera test",
                "roles": ["admin"],
                "keywords": ["camera", "usb", "kiem tra"],
                "text": "Nếu Camera USB mất tín hiệu, kiểm tra nguồn USB, quyền camera, ánh sáng và tab Giám sát trước.",
                "enabled": True,
            },
        )
        assert created.status_code == 200
        entry = next(item for item in created.json()["entries"] if item["title"] == "Quy trình kiểm tra camera test")
        assert entry["source"] == "local"
        assert entry["enabled"] is True

        patched = client.patch(
            f"/api/admin/knowledge/{entry['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"enabled": False},
        )
        assert patched.status_code == 200
        patched_entry = next(item for item in patched.json()["entries"] if item["id"] == entry["id"])
        assert patched_entry["enabled"] is False

        evaluated = client.post(
            "/api/admin/knowledge/evaluate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role": "user", "question": "Lam sao tang diem Eco Score va giam rac tai che ban?"},
        )
        assert evaluated.status_code == 200
        body = evaluated.json()
        assert body["role"] == "user"
        assert body["payload_chars"] > 0
        assert any("Eco Score" in item["title"] for item in body["snippets"])
    finally:
        runtime.close()


def test_admin_knowledge_reports_invalid_local_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    from app.agent.chat_knowledge_service import local_knowledge_path

    path = local_knowledge_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not-json", encoding="utf-8")
    AuthService().create_account("admin", "admin-pass-123", "admin")
    client, runtime = _client(tmp_path)
    try:
        token = client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "admin-pass-123"},
        ).json()["token"]
        res = client.get("/api/admin/knowledge", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "local_error"
        assert body["error"]
        assert body["total"] >= 10
    finally:
        runtime.close()


def test_user_advisor_uses_deepseek_with_aggregate_payload_only(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "api-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-test")
    capture: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Hay uu tien binh nuoc ca nhan."}}]}

    class FakeClient:
        def __init__(self, timeout):
            capture["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, headers, json):
            capture["url"] = url
            capture["headers"] = headers
            capture["body"] = json
            return FakeResponse()

    monkeypatch.setattr("app.agent.ai_chat_service.httpx.Client", FakeClient)
    client, runtime = _client(tmp_path)
    service = HistoryService(runtime.history_file)
    try:
        service.insert(
            track_id=1,
            ts=datetime.now(UTC),
            cls_id=1,
            cls_name="Plastic bottle",
            conf=0.9,
            bbox=(1, 2, 20, 22),
            image_path="C:/secret/raw.jpg",
        )
    finally:
        service.close()

    try:
        res = client.post(
            "/api/user/advisor",
            json={"range_days": 30, "question": "Tôi nên thay đổi gì?"},
        )
        body = res.json()

        assert res.status_code == 200
        assert body["available"] is True
        assert body["model"] == "deepseek-v4-flash"
        assert body["provider"] == "deepseek"
        assert "binh nuoc" in body["message"]
        request_body = capture["body"]
        request_text = json.dumps(request_body, ensure_ascii=False)
        user_payload = json.loads(request_body["messages"][1]["content"])
        assert capture["url"] == "https://api.deepseek.com/chat/completions"
        assert capture["headers"]["Authorization"] == "Bearer api-key"
        assert request_body["model"] == "deepseek-v4-flash"
        assert request_body["thinking"] == {"type": "disabled"}
        assert user_payload["profile"] == "trash_sorter_user"
        assert user_payload["knowledge"]
        assert body["profile"] == "trash_sorter_user"
        assert body["knowledge_used"]
        assert "route_totals" in request_text
        assert "top_classes" in request_text
        assert "C:/secret" not in request_text
        assert "image_path" not in request_text
        assert "annotated_path" not in request_text
        assert "meta_path" not in request_text
        assert "raw_log_line" not in request_text
    finally:
        runtime.close()


def test_user_chat_uses_owned_context_and_knowledge_pack(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "api-key")
    AuthService().create_account("alice", "alice-pass-123", "user")
    AuthService().create_account("bob", "bob-pass-123", "user")
    accounts = {row["username"]: row for row in AuthService().list_accounts()}
    capture: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "Eco Score cua ban dang on."}}]}

    class FakeClient:
        def __init__(self, timeout):
            capture["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, headers, json):
            capture["url"] = url
            capture["headers"] = headers
            capture["body"] = json
            return FakeResponse()

    monkeypatch.setattr("app.agent.ai_chat_service.httpx.Client", FakeClient)
    client, runtime = _client(tmp_path)
    service = HistoryService(runtime.history_file)
    try:
        service.insert(
            track_id=1,
            ts=datetime.now(UTC),
            cls_id=1,
            cls_name="Plastic bottle",
            conf=0.9,
            bbox=(1, 2, 20, 22),
            image_path="C:/alice/private.jpg",
            owner_account_id=int(accounts["alice"]["id"]),
            owner_username="alice",
        )
        service.insert(
            track_id=2,
            ts=datetime.now(UTC),
            cls_id=2,
            cls_name="Organic",
            conf=0.9,
            bbox=(1, 2, 20, 22),
            image_path="C:/bob/private.jpg",
            owner_account_id=int(accounts["bob"]["id"]),
            owner_username="bob",
        )
    finally:
        service.close()

    try:
        login = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pass-123"})
        token = login.json()["token"]
        res = client.post(
            "/api/user/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Giai thich Eco Score va rac tai che cua toi"},
        )
        body = res.json()
        request_body = capture["body"]
        user_payload = json.loads(request_body["messages"][1]["content"])
        request_text = json.dumps(request_body, ensure_ascii=False)

        assert res.status_code == 200
        assert body["profile"] == "trash_sorter_user"
        assert body["knowledge_used"]
        assert user_payload["profile"] == "trash_sorter_user"
        assert user_payload["context"]["total"] == 1
        assert user_payload["context"]["top_classes"][0]["cls_name"] == "Plastic bottle"
        assert "Organic" not in request_text
        assert "C:/alice" not in request_text
        assert "C:/bob" not in request_text
        assert "image_path" not in request_text
        assert token not in request_text
    finally:
        runtime.close()


def test_user_chat_without_deepseek_key_returns_backend_env_hint(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    AuthService().create_account("alice", "alice-pass-123", "user")
    client, runtime = _client(tmp_path)
    try:
        login = client.post("/api/auth/login", json={"username": "alice", "password": "alice-pass-123"})
        token = login.json()["token"]
        res = client.post(
            "/api/user/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": "Chatbot da san sang chua?"},
        )
        body = res.json()

        assert res.status_code == 200
        assert body["available"] is False
        assert body["provider"] == "deepseek"
        assert "DEEPSEEK_API_KEY" in body["message"]
        assert ".env.local" in body["message"]
    finally:
        runtime.close()


def test_admin_chat_uses_sanitized_system_context_and_blocks_user(tmp_path, monkeypatch):
    monkeypatch.setenv("TRASH_SORTER_AUTH_DB", str(tmp_path / "auth.db"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "api-key")
    AuthService().create_account("admin", "admin-pass-123", "admin")
    AuthService().create_account("viewer", "viewer-pass-123", "user")
    capture: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": "He thong on dinh."}}]}

    class FakeClient:
        def __init__(self, timeout):
            capture["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, headers, json):
            capture["url"] = url
            capture["headers"] = headers
            capture["body"] = json
            return FakeResponse()

    monkeypatch.setattr("app.agent.ai_chat_service.httpx.Client", FakeClient)
    client, runtime = _client(tmp_path)
    service = HistoryService(runtime.history_file)
    try:
        service.insert(
            track_id=1,
            ts=datetime.now(UTC),
            cls_id=1,
            cls_name="Plastic bottle",
            conf=0.9,
            bbox=(1, 2, 20, 22),
            image_path="C:/secret/raw.jpg",
            annotated_path="C:/secret/annotated.jpg",
            meta_path="C:/secret/meta.json",
        )
    finally:
        service.close()

    try:
        admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "admin-pass-123"})
        admin_token = admin_login.json()["token"]
        user_login = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer-pass-123"})
        user_token = user_login.json()["token"]

        blocked = client.post(
            "/api/admin/chat",
            headers={"Authorization": f"Bearer {user_token}"},
            json={"message": "Tom tat he thong"},
        )
        assert blocked.status_code == 403

        res = client.post(
            "/api/admin/chat",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"message": "Tom tat he thong"},
        )
        body = res.json()
        assert res.status_code == 200
        assert body["available"] is True
        assert body["role"] == "admin"
        assert body["profile"] == "trash_sorter_admin"
        assert body["knowledge_used"]
        request_text = json.dumps(capture["body"], ensure_ascii=False)
        admin_payload = json.loads(capture["body"]["messages"][1]["content"])
        assert capture["url"] == "https://api.deepseek.com/chat/completions"
        assert admin_payload["profile"] == "trash_sorter_admin"
        assert admin_payload["knowledge"]
        assert "analytics" in request_text
        assert "runtime" in request_text
        assert "C:/secret" not in request_text
        assert "image_path" not in request_text
        assert "annotated_path" not in request_text
        assert "meta_path" not in request_text
        assert admin_token not in request_text
        assert user_token not in request_text
    finally:
        runtime.close()


def test_camera_start_without_usb_keeps_runtime_off(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.setattr("app.agent.runtime.probe_usb_cameras", lambda: [])
    monkeypatch.setattr("app.agent.runtime.read_shared_frame", lambda: None)
    monkeypatch.setattr(
        "app.agent.runtime.shared_frame_diagnostics",
        lambda: {"exists": False, "stale": True, "reason": "no shared frame"},
    )
    client, runtime = _client(tmp_path)
    try:
        res = client.post("/api/camera/start")
        assert res.status_code == 200
        assert res.json()["ok"] is False
        status = client.get("/api/status").json()
        assert status["camera"]["running"] is False
        assert status["current_source"] == ""
        assert status["camera_diagnostics"]["usable"] is False
    finally:
        runtime.close()


def test_camera_start_black_usb_forces_actuation_off(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.setattr(
        "app.agent.runtime.probe_usb_cameras",
        lambda: [
            {
                "source": "1 (DSHOW)",
                "name": "USB Camera",
                "opened": True,
                "usable": False,
                "reason": "black frame",
            }
        ],
    )
    monkeypatch.setattr("app.agent.runtime.read_shared_frame", lambda: None)
    monkeypatch.setattr(
        "app.agent.runtime.shared_frame_diagnostics",
        lambda: {"exists": True, "stale": False, "black_frame": True, "reason": "black frame"},
    )
    client, runtime = _client(tmp_path)
    try:
        assert client.put("/api/actuation/test-mode", json={"enabled": True}).json()["enabled"] is True
        res = client.post("/api/camera/start")
        assert res.status_code == 200
        assert res.json()["ok"] is False
        status = client.get("/api/status").json()
        assert status["camera"]["running"] is False
        assert status["camera_diagnostics"]["reason"] == "USB Camera detected but frame is black"
        assert client.get("/api/actuation/test-mode").json()["enabled"] is False
    finally:
        runtime.close()


def test_dataset_summary_and_sync_catalog(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        before = client.get("/api/dataset/summary").json()
        assert before["images"] == 1
        assert before["catalog_total"] == 0
        assert before["out_of_sync"] is True
        assert before["needs_sync"] is True

        sync = client.post("/api/dataset/sync").json()
        assert sync["count"] == 1

        after = client.get("/api/dataset/summary").json()
        assert after["catalog_total"] == 1
        assert after["box_catalog_total"] == 1
        assert after["class_catalog_total"] == 1
        assert after["out_of_sync"] is False
        assert after["needs_sync"] is False
    finally:
        runtime.close()


def test_dataset_items_lists_catalog_rows(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 1
        res = client.get("/api/dataset/items?limit=20")
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert body["rows"][0]["source"] == "manual_import"
        assert body["rows"][0]["cls_name"] == "Paper"
        assert body["rows"][0]["box_count"] == 1
        assert body["rows"][0]["trusted"] is True
    finally:
        runtime.close()


def test_dataset_items_filters_source_and_class(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 1
        assert client.get("/api/dataset/items?source=roboflow").json()["total"] == 0
        body = client.get("/api/dataset/items?source=manual_import&cls_name=Paper").json()
        assert body["total"] == 1
        assert body["rows"][0]["item_id"] == "manual_abc"
    finally:
        runtime.close()


def test_dataset_items_filters_search_and_trusted_state(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 1
        item_path = str(queue_dir / "manual_abc.jpg")
        mark = client.post(
            "/api/dataset/bulk",
            json={"action": "mark_untrusted", "image_paths": [item_path]},
        )
        assert mark.status_code == 200
        assert mark.json()["count"] == 1
        assert client.get("/api/dataset/items?trusted=true").json()["total"] == 0
        untrusted = client.get("/api/dataset/items?trusted=false&search=manual_abc").json()
        assert untrusted["total"] == 1
        assert untrusted["rows"][0]["trusted"] is False

        restore = client.post(
            "/api/dataset/bulk",
            json={"action": "mark_trusted", "image_paths": [item_path]},
        )
        assert restore.json()["count"] == 1
        assert client.get("/api/dataset/items?trusted=true&search=manual_abc").json()["total"] == 1
    finally:
        runtime.close()


def test_dataset_items_filter_includes_unreviewed_auto_low_conf(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_auto_queue_item(queue_dir, reviewed=False)
    _make_auto_queue_item(queue_dir, reviewed=True)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 2
        summary = client.get("/api/dataset/summary").json()
        assert summary["needs_review_total"] == 1
        assert summary["trainable_total"] == 1
        needs_review = client.get("/api/dataset/items?trusted=false&source=auto_low_conf").json()
        reviewed = client.get("/api/dataset/items?trusted=true&source=auto_low_conf").json()

        assert needs_review["total"] == 1
        assert needs_review["rows"][0]["item_id"] == "auto_raw"
        assert needs_review["rows"][0]["reviewed"] is False
        assert needs_review["rows"][0]["trusted"] is False
        assert reviewed["total"] == 1
        assert reviewed["rows"][0]["item_id"] == "auto_reviewed"
    finally:
        runtime.close()


def test_dataset_item_annotation_get_and_put_boxes(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 1
        before = client.get("/api/dataset/items/manual_abc").json()
        assert before["boxes"][0]["cls_name"] == "Paper"

        payload = {
            "boxes": [
                {"cls_id": 18, "cls_name": "Paper", "conf": 1.0, "xyxy": [1, 2, 20, 12]},
                {"cls_id": 24, "cls_name": "Plastic bottle", "conf": 1.0, "xyxy": [4, 5, 24, 20]},
            ]
        }
        saved = client.put("/api/dataset/items/manual_abc/boxes", json=payload)
        assert saved.status_code == 200
        body = saved.json()
        assert body["item"]["box_count"] == 2
        assert [box["cls_name"] for box in body["boxes"]] == ["Paper", "Plastic bottle"]
        summary = client.get("/api/dataset/summary").json()
        assert summary["box_catalog_total"] == 2
        meta = json.loads((queue_dir / "manual_abc.json").read_text(encoding="utf-8"))
        assert meta["reviewed"] is True
        assert len(meta["boxes"]) == 2
    finally:
        runtime.close()


def test_dataset_item_annotation_canonicalizes_common_aliases(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 1

        payload = {
            "boxes": [
                {"cls_id": 999, "cls_name": "vo chuoi", "conf": 1.0, "xyxy": [1, 2, 20, 12]},
                {"cls_id": 999, "cls_name": "lon nuoc", "conf": 1.0, "xyxy": [4, 5, 24, 20]},
            ]
        }
        saved = client.put("/api/dataset/items/manual_abc/boxes", json=payload)

        assert saved.status_code == 200
        body = saved.json()
        assert [box["cls_name"] for box in body["boxes"]] == ["Organic", "Aluminum can"]
        assert [box["cls_id"] for box in body["boxes"]] == [17, 1]
        meta = json.loads((queue_dir / "manual_abc.json").read_text(encoding="utf-8"))
        assert [box["cls_name"] for box in meta["boxes"]] == ["Organic", "Aluminum can"]
    finally:
        runtime.close()


def test_dataset_bulk_delete_selected_items(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 1
        item_path = str(queue_dir / "manual_abc.jpg")
        deleted = client.post(
            "/api/dataset/bulk",
            json={"action": "delete", "image_paths": [item_path]},
        )
        assert deleted.status_code == 200
        assert deleted.json()["count"] == 1
        assert not (queue_dir / "manual_abc.jpg").exists()
        assert client.get("/api/dataset/items").json()["total"] == 0
    finally:
        runtime.close()


def test_dataset_summary_uses_catalog_fast_path_after_sync(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_queue_item(queue_dir)
    try:
        assert client.post("/api/dataset/sync").json()["count"] == 1
        monkeypatch.setattr(
            "app.agent.api.summarize_queue",
            lambda _queue_dir: (_ for _ in ()).throw(AssertionError("slow JSON summary should not run")),
        )
        after = client.get("/api/dataset/summary").json()
        assert after["images"] == 1
        assert after["box_catalog_total"] == 1
        assert after["needs_sync"] is False
    finally:
        runtime.close()


def test_manual_upload_adds_dataset_record(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/dataset/manual",
            data={"cls_name": "Paper", "cls_id": "1"},
            files=[("files", ("paper.jpg", _image_bytes(), "image/jpeg"))],
        )
        assert res.status_code == 200
        assert res.json()["count"] == 1
        summary = client.get("/api/dataset/summary").json()
        assert summary["sources"]["manual_import"] == 1
        assert summary["catalog_total"] == 1
        assert summary["box_catalog_total"] == 1
    finally:
        runtime.close()


def test_manual_upload_adds_missing_class_mapping(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/dataset/manual",
            data={"cls_name": "Custom wrapper", "cls_id": "55"},
            files=[("files", ("custom.jpg", _image_bytes(), "image/jpeg"))],
        )
        assert res.status_code == 200
        mappings = {
            item["class_name"]: item
            for item in client.get("/api/mappings").json()["mappings"]
        }
        assert mappings["Custom wrapper"]["command"] == "R"
        assert mappings["Custom wrapper"]["bin_index"] == 2
    finally:
        runtime.close()


def test_manual_upload_canonicalizes_common_alias_and_mapping(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/dataset/manual",
            data={"cls_name": "lon nuoc", "cls_id": "999"},
            files=[("files", ("can.jpg", _image_bytes(), "image/jpeg"))],
        )
        assert res.status_code == 200
        items = client.get("/api/dataset/items?source=manual_import&limit=1").json()
        assert items["rows"][0]["cls_name"] == "Aluminum can"
        assert items["rows"][0]["cls_id"] == 1
        mappings = {
            item["class_name"]: item
            for item in client.get("/api/mappings").json()["mappings"]
        }
        assert mappings["Aluminum can"]["command"] == "I"
        assert mappings["Aluminum can"]["bin_index"] == 3
    finally:
        runtime.close()


def test_camera_sample_api_adds_mapping_and_saves_sample(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    calls: list[tuple[str, int, bool]] = []

    def fake_capture_camera_sample(
        cls_name: str,
        cls_id: int,
        *,
        use_latest_detection_box: bool = True,
    ) -> Path:
        calls.append((cls_name, cls_id, use_latest_detection_box))
        return tmp_path / "manual_camera_abc123.jpg"

    runtime.capture_camera_sample = fake_capture_camera_sample  # type: ignore[method-assign]
    try:
        res = client.post(
            "/api/dataset/camera-sample",
            json={"cls_name": "Custom tray item", "cls_id": 77},
        )
        assert res.status_code == 200
        assert res.json()["count"] == 1
        assert calls == [("Custom tray item", 77, True)]
        mappings = {
            item["class_name"]: item
            for item in client.get("/api/mappings").json()["mappings"]
        }
        assert mappings["Custom tray item"]["command"] == "R"
        assert mappings["Custom tray item"]["bin_index"] == 2
    finally:
        runtime.close()


def test_camera_sample_api_returns_conflict_when_camera_has_no_frame(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/dataset/camera-sample",
            json={"cls_name": "Pen", "cls_id": 42},
        )
        assert res.status_code == 409
        assert "Camera is not running" in res.json()["detail"]
    finally:
        runtime.close()


def test_capture_session_api_canonicalizes_pen_alias_and_forces_known_id(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    calls: list[tuple[str, int, int, int]] = []

    def fake_start(
        cls_name: str,
        cls_id: int,
        *,
        target_count: int = 24,
        holdout_count: int = 6,
    ) -> dict[str, object]:
        calls.append((cls_name, cls_id, target_count, holdout_count))
        return {
            "active": True,
            "session_id": "capture-test",
            "cls_name": cls_name,
            "cls_id": cls_id,
            "target_count": target_count,
            "holdout_count": holdout_count,
            "accepted_count": 0,
            "training_count": 0,
            "holdout_accepted": 0,
            "rejected_count": 0,
            "last_message": "Ready",
            "last_image_path": "",
        }

    runtime.start_capture_session = fake_start  # type: ignore[method-assign]
    try:
        res = client.post(
            "/api/dataset/capture-session/start",
            json={
                "cls_name": "cây bút",
                "cls_id": 999,
                "target_count": 24,
                "holdout_count": 6,
            },
        )
        assert res.status_code == 200
        assert calls == [("Pen", 42, 24, 6)]
        assert res.json()["active"] is True
    finally:
        runtime.close()


def test_manual_url_import_adds_source_metadata_and_mapping(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.setattr("app.core.dataset_queue._download_image_url", lambda _url: _image_bytes())
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/dataset/manual-url",
            json={
                "urls": ["https://example.test/pen.jpg"],
                "cls_name": "but bi",
                "cls_id": 42,
                "source_page_url": "https://example.test/page",
                "source_license": "CC-BY test",
                "source_author": "Test Author",
                "source_type": "wikimedia",
            },
        )
        assert res.status_code == 200
        assert res.json()["count"] == 1
        items = client.get("/api/dataset/items?source=manual_web_import&limit=1").json()
        assert items["total"] == 1
        meta_path = Path(items["rows"][0]["meta_path"])
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        assert meta["source"] == "manual_web_import"
        assert meta["source_url"] == "https://example.test/pen.jpg"
        assert meta["source_page_url"] == "https://example.test/page"
        assert meta["source_license"] == "CC-BY test"
        assert meta["source_type"] == "wikimedia"
        assert meta["canonical_class"] == "Pen"
        assert meta["reviewed"] is False
        mappings = {
            item["class_name"]: item
            for item in client.get("/api/mappings").json()["mappings"]
        }
        assert mappings["Pen"]["command"] == "R"
        assert mappings["Pen"]["bin_index"] == 2
    finally:
        runtime.close()


def test_manual_url_import_requires_source_rights_metadata(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/dataset/manual-url",
            json={
                "urls": ["https://example.test/pen.jpg"],
                "cls_name": "Pen",
                "cls_id": 42,
            },
        )
        assert res.status_code == 400
        assert "source_page_url" in res.json()["detail"]
    finally:
        runtime.close()


def test_source_quality_endpoint_reports_phase8_targets(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    _make_reviewed_learn_now_item(queue_dir, "pen_source", "Pen")
    try:
        res = client.get("/api/dataset/source-quality")

        assert res.status_code == 200
        body = res.json()
        assert body["total_images"] == 1
        pen = next(item for item in body["classes"] if item["class_name"] == "Pen")
        assert pen["priority"] == "P0"
        assert pen["missing_for_strong_train"] == 23
    finally:
        runtime.close()


def test_mappings_api_returns_seeded_defaults_and_saves_changes(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.get("/api/mappings")
        assert res.status_code == 200
        mappings = res.json()["mappings"]
        assert len(mappings) >= 40

        edited = [dict(item) for item in mappings]
        edited[0]["command"] = "Z"
        edited[0]["bin_index"] = 9
        put = client.put("/api/mappings", json=edited)
        assert put.status_code == 200
        saved = put.json()["mappings"]
        assert saved[0]["command"] == "Z"
        assert saved[0]["bin_index"] == 9
    finally:
        runtime.close()


def test_model_classes_api_returns_runtime_class_ids(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    runtime.model_classes = lambda: {18: "Paper", 24: "Plastic bottle"}  # type: ignore[method-assign]
    try:
        res = client.get("/api/model/classes")
        assert res.status_code == 200
        assert res.json()["classes"] == [
            {"id": 18, "name": "Paper"},
            {"id": 24, "name": "Plastic bottle"},
        ]
    finally:
        runtime.close()


def test_common_waste_catalog_api_returns_canonical_routes(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.get("/api/common-waste/catalog")
        assert res.status_code == 200
        rows = {item["label"]: item for item in res.json()["items"]}

        assert rows["Vo chuoi"]["canonical_class"] == "Organic"
        assert rows["Vo chuoi"]["command"] == "O"
        assert rows["Lon nuoc"]["canonical_class"] == "Aluminum can"
        assert rows["Lon nuoc"]["command"] == "I"
        assert rows["But bi"]["canonical_class"] == "Pen"
        assert rows["But bi"]["command"] == "R"
    finally:
        runtime.close()


def test_learn_now_status_endpoint_maps_alias_to_route(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    for index in range(6):
        _make_reviewed_learn_now_item(queue_dir, f"pen_{index}", "but bi")
    try:
        res = client.get("/api/learn-now/status?cls_name=but%20bi")

        assert res.status_code == 200
        selected = res.json()["selected"]
        assert selected["class_name"] == "Pen"
        assert selected["command"] == "R"
        assert selected["bin_index"] == 2
        assert selected["priority"] == "P0"
        assert selected["ready_for_reference"] is True
        assert selected["ready_for_micro_train"] is True
    finally:
        runtime.close()


def test_learn_now_refresh_references_calls_runtime(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    calls = {"refresh": 0}

    def refresh_manual_references() -> None:
        calls["refresh"] += 1

    runtime.refresh_manual_references = refresh_manual_references  # type: ignore[method-assign]
    try:
        res = client.post("/api/learn-now/refresh-references?cls_name=Pen")

        assert res.status_code == 200
        assert calls["refresh"] == 1
    finally:
        runtime.close()


def test_unknown_learn_capture_saves_pending_item_and_suggests_label(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.delenv("VISION_LABEL_COMMAND", raising=False)
    client, runtime = _client(tmp_path)
    calls: list[tuple[str, int]] = []

    def fake_capture_unknown_learn_sample(
        cls_name: str,
        cls_id: int,
        *,
        suggestions=None,
    ) -> Path:
        calls.append((cls_name, cls_id))
        return tmp_path / "manual_camera_unknown.jpg"

    runtime.capture_unknown_learn_sample = fake_capture_unknown_learn_sample  # type: ignore[method-assign]
    try:
        res = client.post(
            "/api/learn-now/unknown/capture",
            json={"manual_hint": "but bi"},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["hardware_blocked"] is True
        assert calls == [("Unknown object", -1)]
        assert body["suggestions"][0]["canonical_class"] == "Pen"
        assert body["suggestions"][0]["command"] == "R"
        assert body["suggestions"][0]["bin_index"] == 2
    finally:
        runtime.close()


def test_unknown_learn_capture_rejects_unapproved_non_taxonomy_label(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/learn-now/unknown/capture",
            json={"approved_cls_name": "Yoga Mat"},
        )

        assert res.status_code == 400
        assert "45-class" in res.json()["detail"]
    finally:
        runtime.close()


def test_web_discovery_endpoint_is_discovery_only_without_google_config(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_CSE_ID", raising=False)
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/dataset/web-discovery/search",
            json={"cls_name": "Pen", "query": "but bi", "limit": 3},
        )

        assert res.status_code == 200
        body = res.json()
        assert body["available"] is False
        assert body["candidates"] == []
        assert "not configured" in body["message"]
    finally:
        runtime.close()


def test_learn_now_micro_train_requires_reviewed_samples(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.setattr("app.agent.api._training_processes", lambda: [])
    client, runtime = _client(tmp_path)
    try:
        res = client.post(
            "/api/learn-now/micro-train/start",
            json={"cls_name": "Pen", "profile": "micro"},
        )

        assert res.status_code == 409
        assert "reviewed" in res.json()["detail"]
    finally:
        runtime.close()


def test_learn_now_micro_train_start_invokes_candidate_script(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.setattr("app.agent.api._training_processes", lambda: [])
    calls: list[dict[str, object]] = []

    class FakeProcess:
        pid = 4321

    def fake_popen(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return FakeProcess()

    monkeypatch.setattr("app.agent.api.subprocess.Popen", fake_popen)
    client, runtime = _client(tmp_path)
    queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
    for index in range(6):
        _make_reviewed_learn_now_item(queue_dir, f"pen_{index}", "Pen")
    try:
        res = client.post(
            "/api/learn-now/micro-train/start",
            json={"cls_name": "Pen", "profile": "micro"},
        )

        assert res.status_code == 200
        assert res.json()["count"] == 1
        assert calls
        command = calls[0]["command"]
        assert "-File" in command
        assert "start_learn_now_micro_train.ps1" in " ".join(command)
        assert "-ClassName" in command
        assert "Pen" in command
    finally:
        runtime.close()


def test_dataset_import_accepts_source_name_and_remaps_ids(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    client, runtime = _client(tmp_path)
    runtime.model_classes = lambda: {24: "Plastic bottle"}  # type: ignore[method-assign]
    try:
        res = client.post(
            "/api/dataset/import",
            data={"source_name": "candidate_waste"},
            files=[("file", ("dataset.zip", _yolo_zip_bytes(), "application/zip"))],
        )
        assert res.status_code == 200
        assert res.json()["count"] == 1
        summary = client.get("/api/dataset/summary").json()
        assert summary["sources"]["candidate_waste"] == 1
        assert summary["classes"]["Plastic bottle"] == 1
        queue_dir = Path(runtime.cfg.capture.output_dir) / "low_conf_queue"
        meta = json.loads(next(queue_dir.glob("candidate_waste_*.json")).read_text(encoding="utf-8"))
        assert meta["boxes"][0]["cls_id"] == 24
    finally:
        runtime.close()


def test_settings_put_sanitizes_non_usb_camera_and_uart(tmp_path, monkeypatch):
    monkeypatch.delenv("TRASH_SORTER_AGENT_TOKEN", raising=False)
    monkeypatch.setattr("app.agent.runtime.list_serial_ports", lambda: [])
    client, runtime = _client(tmp_path)
    cfg = runtime.cfg.model_copy(deep=True)
    cfg.camera.source = "0"
    cfg.uart.port = "COM3"
    try:
        res = client.put("/api/settings", json=cfg.model_dump(mode="json"))
        assert res.status_code == 200
        saved = res.json()["config"]
        assert saved["camera"]["source"] == ""
        assert saved["uart"]["port"] == ""
    finally:
        runtime.close()
