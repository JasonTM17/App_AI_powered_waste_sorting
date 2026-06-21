"""Contract tests for the Supabase cloud-readiness migration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "supabase" / "migrations" / "202606170001_full_cloud_readiness.sql"
REALTIME_COMPAT_MIGRATION = (
    ROOT / "supabase" / "migrations" / "202606210007_realtime_events_bridge_compat.sql"
)


def test_supabase_migration_declares_required_tables_and_rls() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    required_tables = [
        "profiles",
        "devices",
        "bin_stations",
        "bins",
        "alerts",
        "collection_schedules",
        "collection_events",
        "device_issues",
        "history",
        "knowledge_entries",
        "training_jobs",
        "realtime_events",
    ]
    for table in required_tables:
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql


def test_supabase_migration_scopes_user_realtime_and_admin_only_training() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    for event_name in [
        "bin_status_changed",
        "alert_created",
        "alert_resolved",
        "collection_completed",
        "device_issue_created",
        "device_status_changed",
    ]:
        assert event_name in sql
    assert "create policy \"training_jobs_admin_all\"" in sql
    assert "create policy \"realtime_events_user_read\"" in sql
    assert "public.station_is_assigned(payload ->> 'station_id')" in sql
    assert "profiles_own_update" not in sql


def test_realtime_compat_migration_supports_legacy_schema_without_event_flood() -> None:
    sql = REALTIME_COMPAT_MIGRATION.read_text(encoding="utf-8").lower()
    assert "create table if not exists public.realtime_events" in sql
    assert "to_jsonb(new)" in sql
    assert "new_row ->> 'completed_by', new_row ->> 'actor_username'" in sql
    assert "tg_op = 'insert' or (new_row ->> 'status') is distinct from" in sql
    assert "trg_bins_realtime" in sql
    assert "trg_alerts_realtime" in sql
    assert "trg_devices_realtime" in sql
    assert "alter publication supabase_realtime add table public.realtime_events" in sql
    assert "public.profiles" not in sql
