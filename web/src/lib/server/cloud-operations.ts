import { Pool, type QueryResultRow } from "pg";

import {
  authDatabaseUrl,
  capabilitiesForRole,
  CloudAuthConfigError,
  type CloudAuthIdentity
} from "@/lib/server/cloud-auth";

const DEFAULT_CENTER = { latitude: 10.843195, longitude: 106.7778, zoom: 12 };
const SEED_SOURCE = "supabase_bridge";
const ACTIVE_SQL = "coalesce(active::text, '') not in ('0', 'false', 'f', 'no', '')";
const ADMIN_ROLE_CAPABILITIES = capabilitiesForRole("admin").map(capabilityForId);
const USER_ROLE_CAPABILITIES = capabilitiesForRole("user").map(capabilityForId);

declare global {
  // eslint-disable-next-line no-var
  var trashSorterCloudOperationsPool: Pool | undefined;
}

type DeviceRow = QueryResultRow & {
  id: number | string;
  device_id: string;
  device_name: string;
  location: string | null;
  owner_username: string | null;
  status: string | null;
  message: string | null;
  active: boolean | number;
  created_at: Date | string | null;
  updated_at: Date | string | null;
};

type StationRow = QueryResultRow & {
  id: number | string;
  station_id: string;
  name: string;
  area: string | null;
  address: string | null;
  latitude: number | string | null;
  longitude: number | string | null;
  status: string | null;
  coordinate_verified: boolean | number;
  assigned_owner_username: string | null;
  device_id?: string | null;
  note?: string | null;
  seed_source: string | null;
  active: boolean | number;
  created_at: Date | string | null;
  updated_at: Date | string | null;
};

type BinRow = QueryResultRow & {
  id: number | string;
  bin_id: string;
  station_id: string;
  command: "O" | "R" | "I";
  bin_index: number | string;
  label: string;
  fill_percent: number | string | null;
  status: string | null;
  active: boolean | number;
  updated_at: Date | string | null;
};

type AlertRow = QueryResultRow & {
  id: number | string;
  alert_id: string;
  station_id: string | null;
  bin_id: string | null;
  device_id: string | null;
  severity: string | null;
  title: string;
  message: string | null;
  status: string | null;
  source: string | null;
  created_at: Date | string | null;
  updated_at: Date | string | null;
  resolved_at: Date | string | null;
  actor_username: string | null;
  derived: boolean | number;
};

type ScheduleRow = QueryResultRow & {
  id: number | string;
  schedule_id: string;
  station_id: string;
  station_name: string | null;
  assigned_owner_username: string | null;
  scheduled_date: Date | string;
  window_start: string | null;
  window_end: string | null;
  status: string | null;
  completed_at: Date | string | null;
  completed_by: string | null;
  note: string | null;
  created_at: Date | string | null;
  updated_at: Date | string | null;
};

export function cloudRoleCatalog() {
  return {
    roles: [
      {
        role: "admin",
        label: "Admin",
        capabilities: ADMIN_ROLE_CAPABILITIES,
        description: "Full cloud read access plus local bridge hardware controls."
      },
      {
        role: "user",
        label: "User",
        capabilities: USER_ROLE_CAPABILITIES,
        description: "Scoped cloud operations: assigned map, alerts, schedules, collection, issue report."
      }
    ]
  };
}

export async function cloudDevices() {
  const result = await pool().query<DeviceRow>(
    `select (row_number() over (order by device_id))::int as id,
            device_id, device_name, location, owner_username, status, message,
            active, created_at, updated_at
       from public.devices
      order by device_name, device_id`
  );
  return { devices: result.rows.map(deviceDto) };
}

export async function cloudBinMap(identity: CloudAuthIdentity, includeInactive = false) {
  const owner = identity.role === "admin" ? "" : identity.username;
  const stationRows = await stationRowsForScope(owner, includeInactive);
  const stationIds = stationRows.map((row) => row.station_id);
  const childBinsByStation = await binsByStation(stationIds);
  const alertsByStation = await openAlertCountsByStation(stationIds, owner);
  const stations = stationRows.map((row) => stationDto(row, childBinsByStation.get(row.station_id) ?? [], alertsByStation));
  return {
    generated_at: new Date().toISOString(),
    center: DEFAULT_CENTER,
    stations,
    total: stations.length,
    seed_source: SEED_SOURCE
  };
}

export async function cloudAlerts(identity: CloudAuthIdentity, includeResolved = true) {
  const owner = identity.role === "admin" ? "" : identity.username;
  const stationIds = owner ? (await stationRowsForScope(owner, false)).map((row) => row.station_id) : [];
  const values: unknown[] = [];
  const where: string[] = [];
  if (!includeResolved) {
    where.push("status <> 'resolved'");
  }
  if (owner) {
    values.push(stationIds);
    where.push("(station_id = '' or station_id = any($1::text[]))");
  }
  const result = await pool().query<AlertRow>(
    `select (row_number() over (order by created_at desc, alert_id))::int as id,
            alert_id, station_id, bin_id, device_id, severity, title, message, status,
            source, created_at, updated_at, resolved_at, actor_username, false::boolean as derived
       from public.alerts
      ${where.length ? `where ${where.join(" and ")}` : ""}
      order by created_at desc, alert_id desc`,
    values
  );
  const explicit = result.rows.map(alertDto);
  const derived = await derivedFullnessAlerts(owner, stationIds);
  const byId = new Map<string, ReturnType<typeof alertDto>>();
  [...derived, ...explicit].forEach((item) => byId.set(item.alert_id, item));
  const alerts = [...byId.values()].filter((item) => includeResolved || item.status !== "resolved");
  return { alerts, total: alerts.length };
}

export async function cloudSchedules(identity: CloudAuthIdentity) {
  const owner = identity.role === "admin" ? "" : identity.username;
  const values: unknown[] = [];
  const where: string[] = [];
  if (owner) {
    values.push(owner);
    where.push("s.assigned_owner_username = $1");
  }
  const result = await pool().query<ScheduleRow>(
    `select (row_number() over (order by s.scheduled_date, s.window_start, s.schedule_id))::int as id,
            s.schedule_id, s.station_id, bs.name as station_name, s.assigned_owner_username,
            s.scheduled_date, s.window_start::text, s.window_end::text, s.status,
            s.completed_at, s.completed_by, s.note, s.created_at, s.updated_at
       from public.collection_schedules s
       left join public.bin_stations bs on bs.station_id = s.station_id
      ${where.length ? `where ${where.join(" and ")}` : ""}
      order by s.scheduled_date, s.window_start, s.schedule_id`,
    values
  );
  const schedules = result.rows.map(scheduleDto);
  return { schedules, total: schedules.length };
}

export async function cloudOperationsHealth() {
  const client = pool();
  const [stations, bins, schedules] = await Promise.all([
    client.query<{ count: string }>("select count(*)::text as count from public.bin_stations"),
    client.query<{ count: string }>("select count(*)::text as count from public.bins"),
    client.query<{ count: string }>("select count(*)::text as count from public.collection_schedules")
  ]);
  const stationTotal = Number(stations.rows[0]?.count ?? 0);
  const binTotal = Number(bins.rows[0]?.count ?? 0);
  const scheduleTotal = Number(schedules.rows[0]?.count ?? 0);
  return {
    ok: stationTotal > 0 && binTotal > 0,
    path: "supabase:cloud",
    station_total: stationTotal,
    bin_total: binTotal,
    schedule_total: scheduleTotal,
    seed_source: SEED_SOURCE
  };
}

export async function cloudPatchAlert(alertId: string, status: "open" | "acknowledged" | "resolved", actor: string) {
  await pool().query(
    `update public.alerts
        set status = $2,
            actor_username = $3,
            resolved_at = case when $2 = 'resolved' then now() else null end,
            updated_at = now()
      where alert_id = $1`,
    [alertId, status, actor]
  );
}

export async function cloudCompleteCollection(
  identity: CloudAuthIdentity,
  scheduleId: string,
  note: string
) {
  const owner = identity.username;
  const result = await pool().query<ScheduleRow>(
    `update public.collection_schedules
        set status = 'completed',
            completed_at = coalesce(completed_at, now()),
            completed_by = coalesce(nullif(completed_by, ''), $3),
            note = coalesce(nullif($4::text, ''), note),
            updated_at = now()
      where schedule_id = $1
        and ($2::text = '' or assigned_owner_username = $2)
      returning 1::int as id, schedule_id, station_id, ''::text as station_name,
                assigned_owner_username, scheduled_date, window_start::text, window_end::text, status,
                completed_at, completed_by, note, created_at, updated_at`,
    [scheduleId, identity.role === "admin" ? "" : owner, owner || "user", note]
  );
  const row = result.rows[0];
  if (!row) {
    return null;
  }
  await recordCollectionEvent(row.schedule_id, row.station_id, owner || "user", note);
  return scheduleDto(row);
}

export async function cloudCreateDeviceIssue(identity: CloudAuthIdentity, payload: Record<string, unknown>) {
  const issueId = `issue-${cryptoRandom()}`;
  const alertId = `alert-${cryptoRandom()}`;
  const stationId = text(payload.station_id);
  if (identity.role !== "admin") {
    const scoped = await stationRowsForScope(identity.username, false);
    if (stationId && !scoped.some((station) => station.station_id === stationId)) {
      return null;
    }
  }
  const issueType = text(payload.issue_type) || "other";
  const severity = ["info", "warning", "danger"].includes(text(payload.severity)) ? text(payload.severity) : "warning";
  const description = text(payload.description);
  const binId = text(payload.bin_id);
  const deviceId = text(payload.device_id);
  const result = await pool().query(
    `insert into public.device_issues
       (issue_id, station_id, bin_id, device_id, issue_type, severity, description,
        status, reporter_username, alert_id, created_at, updated_at)
     values ($1, $2, $3, $4, $5, $6, $7, 'open', $8, $9, now(), now())
     returning 1::int as id, issue_id, station_id, bin_id, device_id, issue_type,
               severity, description, status, reporter_username, null::int as reporter_account_id,
               alert_id, created_at, updated_at, resolved_at`,
    [issueId, stationId, binId, deviceId, issueType, severity, description, identity.username, alertId]
  );
  await pool().query(
    `insert into public.alerts
       (alert_id, station_id, bin_id, device_id, severity, title, message, status, source,
        actor_username, created_at, updated_at)
     values ($1, $2, $3, $4, $5, $6, $7, 'open', 'device_issue', $8, now(), now())`,
    [alertId, stationId, binId, deviceId, severity, issueTitle(issueType), description, identity.username]
  );
  return { issue: result.rows[0], message: "Device issue reported" };
}

async function recordCollectionEvent(scheduleId: string, stationId: string, actor: string, note: string) {
  try {
    await pool().query(
      `insert into public.collection_events(schedule_id, station_id, completed_by, note)
       values ($1, $2, $3, $4)`,
      [scheduleId, stationId, actor, note]
    );
  } catch {
    await pool().query(
      `insert into public.collection_events(schedule_id, station_id, actor_username, note)
       values ($1, $2, $3, $4)`,
      [scheduleId, stationId, actor, note]
    ).catch(() => undefined);
  }
}

async function stationRowsForScope(ownerUsername: string, includeInactive: boolean) {
  const values: unknown[] = [];
  const where: string[] = [];
  if (!includeInactive) {
    where.push(ACTIVE_SQL);
  }
  if (ownerUsername) {
    values.push(ownerUsername);
    where.push(`assigned_owner_username = $${values.length}`);
  }
  const result = await pool().query<StationRow>(
    `select (row_number() over (order by station_id))::int as id,
            station_id, name, area, address, latitude, longitude, status,
            coordinate_verified, assigned_owner_username, ''::text as device_id, ''::text as note,
            'supabase_bridge'::text as seed_source, active, created_at, updated_at
       from public.bin_stations
      ${where.length ? `where ${where.join(" and ")}` : ""}
      order by station_id`,
    values
  );
  return result.rows;
}

async function binsByStation(stationIds: string[]) {
  const out = new Map<string, ReturnType<typeof binDto>[]>();
  if (stationIds.length === 0) {
    return out;
  }
  const fillColumn = await columnExpression("bins", ["fill_percent", "fullness_percent"], "0");
  const result = await pool().query<BinRow>(
    `select (row_number() over (order by station_id, bin_index))::int as id,
            bin_id, station_id, command, bin_index, label, ${fillColumn} as fill_percent, status, active, updated_at
       from public.bins
      where station_id = any($1::text[])
      order by station_id, bin_index`,
    [stationIds]
  );
  for (const row of result.rows) {
    const list = out.get(row.station_id) ?? [];
    list.push(binDto(row));
    out.set(row.station_id, list);
  }
  return out;
}

async function openAlertCountsByStation(stationIds: string[], ownerUsername: string) {
  const out: Record<string, Record<string, number>> = {};
  if (stationIds.length === 0) {
    return out;
  }
  const result = await pool().query<{ station_id: string; severity: string; count: string }>(
    `select station_id, severity, count(*)::text as count
       from public.alerts
      where status <> 'resolved'
        and station_id = any($1::text[])
        and ($2::text = '' or station_id in (
          select station_id from public.bin_stations where assigned_owner_username = $2
        ))
      group by station_id, severity`,
    [stationIds, ownerUsername]
  );
  result.rows.forEach((row) => {
    out[row.station_id] = out[row.station_id] ?? {};
    out[row.station_id][row.severity] = Number(row.count);
  });
  return out;
}

async function derivedFullnessAlerts(ownerUsername: string, stationIds: string[]) {
  const scopedStationIds = ownerUsername ? stationIds : undefined;
  const fillColumn = await columnExpression("bins", ["fill_percent", "fullness_percent"], "0");
  const fillExpr = fillColumn === "0" ? "0" : `b.${fillColumn}`;
  const values: unknown[] = [];
  const where = [`coalesce(b.active::text, '') not in ('0', 'false', 'f', 'no', '')`, `(${fillExpr} >= 80 or b.status in ('warning', 'full'))`];
  if (scopedStationIds) {
    values.push(scopedStationIds);
    where.push("b.station_id = any($1::text[])");
  }
  const result = await pool().query<BinRow>(
    `select (row_number() over (order by b.station_id, b.bin_index))::int as id,
            b.bin_id, b.station_id, b.command, b.bin_index, b.label,
            ${fillExpr} as fill_percent, b.status, b.active, b.updated_at
       from public.bins b
      where ${where.join(" and ")}
      order by ${fillExpr} desc, b.updated_at desc`,
    values
  );
  const now = new Date().toISOString();
  return result.rows.map((row, index) => {
    const fill = number(row.fill_percent);
    const danger = row.status === "full" || fill >= 95;
    const label = displayBinLabel(Number(row.bin_index), row.label);
    return {
      id: index + 1,
      alert_id: `derived-fullness-${row.bin_id}`,
      station_id: row.station_id,
      bin_id: row.bin_id,
      device_id: "",
      severity: danger ? "danger" : "warning",
      title: danger ? "Thùng rác đã đầy" : "Thùng rác gần đầy",
      message: `Thùng ${label} ${danger ? "đã đầy" : "gần đầy"} ${Math.round(fill)}%.`,
      status: "open",
      source: "derived_fullness",
      created_at: iso(row.updated_at) || now,
      updated_at: iso(row.updated_at) || now,
      resolved_at: "",
      actor_username: "",
      derived: true
    };
  });
}

function pool() {
  const databaseUrl = authDatabaseUrl();
  if (!databaseUrl) {
    throw new CloudAuthConfigError();
  }
  if (!globalThis.trashSorterCloudOperationsPool) {
    globalThis.trashSorterCloudOperationsPool = new Pool({
      connectionString: stripPgSslParams(databaseUrl),
      max: 3,
      ssl: shouldUseSsl(databaseUrl) ? { rejectUnauthorized: false } : undefined
    });
  }
  return globalThis.trashSorterCloudOperationsPool;
}

async function columnExpression(tableName: string, candidates: string[], fallback: string) {
  const result = await pool().query<{ column_name: string }>(
    `select column_name
       from information_schema.columns
      where table_schema = 'public'
        and table_name = $1
        and column_name = any($2::text[])`,
    [tableName, candidates]
  );
  const existing = new Set(result.rows.map((row) => row.column_name));
  return candidates.find((candidate) => existing.has(candidate)) ?? fallback;
}

function deviceDto(row: DeviceRow) {
  return {
    id: Number(row.id),
    device_id: row.device_id,
    device_name: row.device_name,
    location: row.location ?? "",
    owner_username: row.owner_username ?? "",
    status: row.status ?? "offline",
    message: row.message ?? "",
    active: boolean(row.active),
    created_at: iso(row.created_at),
    updated_at: iso(row.updated_at)
  };
}

function binDto(row: BinRow) {
  const fill = number(row.fill_percent);
  return {
    id: Number(row.id),
    bin_id: row.bin_id,
    station_id: row.station_id,
    command: row.command,
    bin_index: Number(row.bin_index),
    label: row.label,
    fullness_percent: row.fill_percent === null ? null : fill,
    fill_percent: fill,
    status: row.status || fullnessStatus(fill),
    active: boolean(row.active),
    updated_at: iso(row.updated_at)
  };
}

function stationDto(
  row: StationRow,
  bins: ReturnType<typeof binDto>[],
  alertsByStation: Record<string, Record<string, number>>
) {
  const alertCounts = alertsByStation[row.station_id] ?? {};
  const openAlertTotal = Object.values(alertCounts).reduce((sum, value) => sum + value, 0);
  return {
    id: Number(row.id),
    station_id: row.station_id,
    name: row.name,
    area: row.area ?? "",
    address: row.address ?? "",
    latitude: row.latitude === null ? null : number(row.latitude),
    longitude: row.longitude === null ? null : number(row.longitude),
    status: row.status ?? "candidate",
    coordinate_verified: boolean(row.coordinate_verified),
    source: row.seed_source ?? "",
    seed_source: row.seed_source ?? "",
    assigned_owner_username: row.assigned_owner_username ?? "",
    owner_username: row.assigned_owner_username ?? "",
    device_id: row.device_id ?? "",
    note: row.note ?? "",
    active: boolean(row.active),
    created_at: iso(row.created_at),
    updated_at: iso(row.updated_at),
    bins,
    alert_counts: alertCounts,
    alert_total: openAlertTotal,
    open_alert_total: openAlertTotal
  };
}

function alertDto(row: AlertRow) {
  return {
    id: Number(row.id),
    alert_id: row.alert_id,
    station_id: row.station_id ?? "",
    bin_id: row.bin_id ?? "",
    device_id: row.device_id ?? "",
    severity: row.severity ?? "info",
    title: row.title,
    message: row.message ?? "",
    status: row.status ?? "open",
    source: row.source ?? "manual",
    created_at: iso(row.created_at),
    updated_at: iso(row.updated_at),
    resolved_at: iso(row.resolved_at),
    actor_username: row.actor_username ?? "",
    derived: boolean(row.derived)
  };
}

function scheduleDto(row: ScheduleRow) {
  const scheduledDate = dateOnly(row.scheduled_date);
  const completed = Boolean(row.completed_at);
  const state = scheduleState(row.status ?? "scheduled", scheduledDate, completed);
  return {
    id: Number(row.id),
    schedule_id: row.schedule_id,
    station_id: row.station_id,
    station_name: row.station_name || row.station_id,
    assigned_owner_username: row.assigned_owner_username ?? "",
    scheduled_date: scheduledDate,
    window_start: String(row.window_start ?? ""),
    window_end: String(row.window_end ?? ""),
    status: row.status ?? "scheduled",
    state,
    completed_at: row.completed_at ? iso(row.completed_at) : null,
    completed_by: row.completed_by ?? "",
    note: row.note ?? "",
    created_at: iso(row.created_at),
    updated_at: iso(row.updated_at)
  };
}

function scheduleState(status: string, scheduledDate: string, completed: boolean) {
  if (completed || status === "completed") {
    return "completed";
  }
  if (status !== "scheduled") {
    return status;
  }
  const today = new Date().toISOString().slice(0, 10);
  if (scheduledDate < today) {
    return "overdue";
  }
  if (scheduledDate === today) {
    return "due_today";
  }
  return "upcoming";
}

function capabilityForId(id: string) {
  return {
    id,
    label: id,
    description: id.startsWith("admin.") ? "Admin-only capability" : "Role capability"
  };
}

function issueTitle(issueType: string) {
  const labels: Record<string, string> = {
    full_bin: "Thùng đầy",
    sensor_problem: "Lỗi cảm biến",
    camera_problem: "Lỗi camera",
    servo_problem: "Lỗi servo",
    audio_problem: "Lỗi audio",
    dirty_bin: "Thùng bẩn"
  };
  return labels[issueType] ?? "Báo lỗi thiết bị";
}

function displayBinLabel(index: number, fallback: string) {
  if (index === 1) return "Hữu cơ";
  if (index === 2) return "Vô cơ";
  if (index === 3) return "Tái chế";
  return fallback;
}

function fullnessStatus(fill: number) {
  if (fill >= 95) return "full";
  if (fill >= 80) return "warning";
  return "normal";
}

function iso(value: Date | string | null | undefined) {
  if (!value) return "";
  if (value instanceof Date) return value.toISOString();
  return String(value);
}

function dateOnly(value: Date | string) {
  return value instanceof Date ? value.toISOString().slice(0, 10) : String(value).slice(0, 10);
}

function number(value: number | string | null | undefined) {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

function boolean(value: boolean | number) {
  return value === true || value === 1;
}

function text(value: unknown) {
  return String(value ?? "").trim();
}

function cryptoRandom() {
  return Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
}

function shouldUseSsl(databaseUrl: string) {
  try {
    const parsed = new URL(databaseUrl);
    return !["localhost", "127.0.0.1"].includes(parsed.hostname);
  } catch {
    return true;
  }
}

function stripPgSslParams(databaseUrl: string) {
  try {
    const parsed = new URL(databaseUrl);
    parsed.searchParams.delete("sslmode");
    parsed.searchParams.delete("sslcert");
    parsed.searchParams.delete("sslkey");
    parsed.searchParams.delete("sslrootcert");
    return parsed.toString();
  } catch {
    return databaseUrl;
  }
}
