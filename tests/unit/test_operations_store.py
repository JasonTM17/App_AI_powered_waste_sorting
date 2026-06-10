from app.agent.operations_store import OperationsStore


def test_operations_store_seeds_real_map_and_is_idempotent(tmp_path):
    db_path = tmp_path / "operations.db"

    store = OperationsStore(db_path)
    try:
        health = store.health()
        assert health["ok"] is True
        assert health["station_total"] == 10
        assert health["bin_total"] == 30
        assert health["schedule_total"] == 10

        bin_map = store.list_bin_map()
        assert bin_map["total"] == 10
        assert len(bin_map["stations"]) == 10
        assert all(station["coordinate_verified"] is False for station in bin_map["stations"])
        assert all(len(station["bins"]) == 3 for station in bin_map["stations"])

        roles = store.list_role_catalog()
        admin_caps = set(next(role for role in roles if role["role"] == "admin")["capabilities"])
        user_caps = set(next(role for role in roles if role["role"] == "user")["capabilities"])
        assert "admin.bin_map.manage" in admin_caps
        assert "user.device_issues.create" in user_caps
    finally:
        store.close()

    store = OperationsStore(db_path)
    try:
        assert store.health()["station_total"] == 10
        assert len(store.list_schedules()) == 10
    finally:
        store.close()


def test_complete_collection_is_idempotent_and_records_events(tmp_path):
    store = OperationsStore(tmp_path / "operations.db")
    try:
        schedule = store.list_schedules()[0]

        first = store.complete_collection(
            str(schedule["schedule_id"]),
            actor_username="tester",
            actor_account_id=1,
            note="first pass",
        )
        second = store.complete_collection(
            str(schedule["schedule_id"]),
            actor_username="tester",
            actor_account_id=1,
            note="second pass",
        )

        assert first is not None
        assert first["already_completed"] is False
        assert second is not None
        assert second["already_completed"] is True
        assert store.list_schedules()[0]["state"] == "completed"
    finally:
        store.close()


def test_device_issue_creates_alert_and_is_visible_in_summary(tmp_path):
    store = OperationsStore(tmp_path / "operations.db")
    try:
        issue = store.create_issue(
            {
                "station_id": "td-bin-001",
                "bin_id": "td-bin-001-R",
                "device_id": "dev-thu-duc-001",
                "issue_type": "camera_problem",
                "severity": "warning",
                "description": "Camera feed is unstable",
            },
            reporter_username="tester",
            reporter_account_id=99,
        )

        assert issue["issue_type"] == "camera_problem"
        assert issue["alert_id"]

        alerts = store.list_alerts(include_resolved=False)
        assert any(alert["alert_id"] == issue["alert_id"] for alert in alerts)
        summary = store.summary()
        assert summary["open_alert_total"] >= 1
        assert summary["issue_counts"]["camera_problem"] >= 1
    finally:
        store.close()
