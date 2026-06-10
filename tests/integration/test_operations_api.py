from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.api import create_app
from app.agent.runtime import AgentRuntime
from app.core.config import AppConfig, save_config


def _runtime(base: Path) -> AgentRuntime:
    config_path = base / "config.json"
    cfg = AppConfig()
    cfg.capture.output_dir = str(base / "dataset_v2")
    save_config(cfg, config_path)
    return AgentRuntime(
        config_file=config_path,
        history_file=base / "history.db",
        dataset_file=base / "dataset.db",
        operations_file=base / "operations.db",
    )


def test_admin_and_user_operations_routes_work_and_stay_scoped(monkeypatch, tmp_path):
    monkeypatch.setenv("TRASH_SORTER_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("TRASH_SORTER_USER_TOKEN", "user-token")
    runtime = _runtime(tmp_path)
    client = TestClient(create_app(runtime=runtime))
    admin_headers = {"Authorization": "Bearer admin-token"}
    user_headers = {"Authorization": "Bearer user-token"}

    try:
        assert client.get("/api/admin/roles", headers=admin_headers).status_code == 200
        assert client.get("/api/admin/roles", headers=user_headers).status_code == 403

        admin_devices = client.get("/api/admin/devices", headers=admin_headers)
        assert admin_devices.status_code == 200
        assert len(admin_devices.json()["devices"]) >= 1

        created_device = client.post(
            "/api/admin/devices",
            headers=admin_headers,
            json={
                "device_id": "dev-thu-duc-qa",
                "device_name": "Thu Duc QA Station",
                "location": "Thu Duc",
                "owner_username": "user",
                "status": "online",
                "message": "smoke",
                "active": True,
            },
        )
        assert created_device.status_code == 200
        assert created_device.json()["device_id"] == "dev-thu-duc-qa"

        patched_station = client.patch(
            "/api/admin/bin-map/td-bin-001",
            headers=admin_headers,
            json={
                "latitude": 10.8025,
                "longitude": 106.7412,
                "coordinate_verified": True,
                "note": "verified in smoke test",
            },
        )
        assert patched_station.status_code == 200
        assert patched_station.json()["coordinate_verified"] is True

        bin_map = client.get("/api/user/bin-map", headers=user_headers)
        assert bin_map.status_code == 200
        assert bin_map.json()["total"] == 10
        assert len(bin_map.json()["stations"]) == 10

        schedules = client.get("/api/user/collection-schedule", headers=user_headers)
        assert schedules.status_code == 200
        first_schedule = schedules.json()["schedules"][0]
        schedule_id = first_schedule["schedule_id"]

        complete = client.post(
            f"/api/user/collections/{schedule_id}/complete",
            headers=user_headers,
            json={"note": "collected during smoke"},
        )
        assert complete.status_code == 200
        assert complete.json()["already_completed"] is False

        duplicate = client.post(
            f"/api/user/collections/{schedule_id}/complete",
            headers=user_headers,
            json={"note": "repeat smoke"},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["already_completed"] is True

        issue = client.post(
            "/api/user/device-issues",
            headers=user_headers,
            json={
                "station_id": "td-bin-001",
                "bin_id": "td-bin-001-R",
                "device_id": "dev-thu-duc-001",
                "issue_type": "camera_problem",
                "severity": "warning",
                "description": "camera feed unstable",
            },
        )
        assert issue.status_code == 200
        issue_payload = issue.json()
        assert issue_payload["issue"]["alert_id"]

        user_alerts = client.get("/api/user/alerts?include_resolved=false", headers=user_headers)
        assert user_alerts.status_code == 200
        assert any(item["alert_id"] == issue_payload["issue"]["alert_id"] for item in user_alerts.json()["alerts"])

        admin_alerts = client.get("/api/admin/alerts", headers=admin_headers)
        assert admin_alerts.status_code == 200
        alert_id = issue_payload["issue"]["alert_id"]
        resolved = client.patch(
            f"/api/admin/alerts/{alert_id}",
            headers=admin_headers,
            json={"status": "resolved"},
        )
        assert resolved.status_code == 200

        operations_health = client.get("/api/admin/operations/health", headers=admin_headers)
        assert operations_health.status_code == 200
        assert operations_health.json()["ok"] is True
    finally:
        runtime.close()
