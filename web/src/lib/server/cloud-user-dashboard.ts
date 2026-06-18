import type { QueryResultRow } from "pg";

import type {
  AnalyticsRangeDays,
  BinFullness,
  DeviceStatus,
  UserAnalytics,
  UserAdvisorResponse,
  UserDevice,
  UserExperience,
  UserHistoryItem,
  UserHistoryResponse,
  UserReport,
  UserRouteTotal,
  WasteClassCount,
  WellnessInsight
} from "@/lib/agent";
import type { CloudAuthIdentity } from "@/lib/server/cloud-auth";
import { cloudAlerts, cloudBinMap, cloudOperationsPool, cloudSchedules } from "@/lib/server/cloud-operations";

const ALLOWED_RANGES = new Set([7, 30, 90, 180]);
const CSV_FIELDS = ["id", "ts", "cls_name", "confidence", "category", "route_label", "bin_index", "ack_status", "device_id"];

type HistoryRow = QueryResultRow & {
  id: number | string;
  ts: Date | string;
  cls_name: string;
  confidence: number | string;
  route_label: string | null;
  bin_index: number | string | null;
  uart_command: string | null;
  ack_status: string | null;
  device_id: string | null;
  image_available: boolean | number;
};

type DeviceRow = QueryResultRow & {
  device_id: string;
  device_name: string;
  location: string | null;
  owner_username: string;
  status: string | null;
  message: string | null;
  last_seen_at: Date | string | null;
};

type BinRow = QueryResultRow & {
  bin_index: number | string;
  label: string;
  station_name: string;
  fill_percent: number | string | null;
  updated_at: Date | string | null;
};

export function cleanAnalyticsRange(raw: string | null): AnalyticsRangeDays {
  const value = Number(raw ?? 30);
  return (ALLOWED_RANGES.has(value) ? value : 30) as AnalyticsRangeDays;
}

export async function cloudUserHistory(
  identity: CloudAuthIdentity,
  options: { limit?: number; offset?: number; rangeDays?: AnalyticsRangeDays } = {}
): Promise<UserHistoryResponse> {
  const limit = Math.max(1, Math.min(100, options.limit ?? 50));
  const offset = Math.max(0, options.offset ?? 0);
  const values: unknown[] = [identity.username];
  let dateFilter = "";
  if (options.rangeDays) {
    values.push(options.rangeDays);
    dateFilter = `and ts >= current_date - ($${values.length}::int - 1) * interval '1 day'`;
  }
  const listValues = [...values, limit, offset];
  const [totalResult, result] = await Promise.all([
    cloudOperationsPool().query<{ count: string }>(
      `select count(*)::text as count from public.history where owner_username = $1 ${dateFilter}`,
      values
    ),
    cloudOperationsPool().query<HistoryRow>(
      `select id, ts, cls_name, confidence, route_label, bin_index, uart_command,
              ack_status, device_id, image_available
         from public.history
        where owner_username = $1 ${dateFilter}
        order by ts desc, id desc
        limit $${listValues.length - 1} offset $${listValues.length}`,
      listValues
    )
  ]);
  return { rows: result.rows.map(historyItem), total: Number(totalResult.rows[0]?.count ?? 0) };
}

export async function cloudUserAnalytics(identity: CloudAuthIdentity, rangeDays: AnalyticsRangeDays): Promise<UserAnalytics> {
  const historyResult = await cloudOperationsPool().query<HistoryRow>(
    `select id, ts, cls_name, confidence, route_label, bin_index, uart_command,
            ack_status, device_id, image_available
       from public.history
      where owner_username = $1
        and ts >= current_date - ($2::int * 2) * interval '1 day'
      order by ts desc, id desc`,
    [identity.username, rangeDays]
  );
  const [deviceStatus, bins] = await Promise.all([scopedDeviceStatus(identity.username), scopedBins(identity.username)]);
  return buildAnalytics(historyResult.rows, deviceStatus, bins, rangeDays);
}

export async function cloudUserDevice(identity: CloudAuthIdentity): Promise<UserDevice> {
  const [deviceStatus, bins, recent] = await Promise.all([
    scopedDeviceStatus(identity.username),
    scopedBins(identity.username),
    cloudUserHistory(identity, { limit: 8 })
  ]);
  deviceStatus.bins = bins;
  return {
    generated_at: new Date().toISOString(),
    device_status: deviceStatus,
    bins,
    recent_activity: recent.rows,
    owner_username: identity.username
  };
}

export async function cloudUserReport(identity: CloudAuthIdentity, rangeDays: AnalyticsRangeDays): Promise<UserReport> {
  const analytics = await cloudUserAnalytics(identity, rangeDays);
  return buildUserReport(analytics, rangeDays);
}

function buildUserReport(analytics: UserAnalytics, rangeDays: AnalyticsRangeDays): UserReport {
  const recycleRate = Math.round(analytics.eco_score.recyclable_rate);
  const delta = analytics.comparison.delta;
  return {
    generated_at: new Date().toISOString(),
    range_days: rangeDays,
    analytics,
    summary_cards: [
      { title: "Tổng lượt phân loại", value: String(analytics.total), detail: `${rangeDays} ngày gần đây`, tone: "neutral" },
      { title: "Eco Score", value: String(analytics.eco_score.score), detail: analytics.eco_score.label, tone: analytics.eco_score.score >= 70 ? "success" : "warning" },
      { title: "Tỷ lệ tái chế", value: `${recycleRate}%`, detail: "Tính từ các lượt đã nhận diện", tone: recycleRate >= 40 ? "success" : "neutral" },
      { title: "So với kỳ trước", value: delta > 0 ? `+${delta}` : String(delta), detail: `${analytics.comparison.delta_percent.toFixed(1)}% thay đổi`, tone: delta > 0 ? "warning" : "success" }
    ],
    export_url: `/api/user/history/export.csv?range_days=${rangeDays}`,
    csv_safe_fields: CSV_FIELDS
  };
}

export async function cloudUserExperience(identity: CloudAuthIdentity, rangeDays: AnalyticsRangeDays): Promise<UserExperience> {
  const analytics = await cloudUserAnalytics(identity, rangeDays);
  return buildUserExperience(analytics, rangeDays);
}

function buildUserExperience(analytics: UserAnalytics, rangeDays: AnalyticsRangeDays): UserExperience {
  const generatedAt = new Date().toISOString();
  const notifications: UserExperience["notifications"] = [];
  if (!analytics.total) notifications.push({ id: "empty-history", title: "Chưa có dữ liệu trong khoảng này", message: "Hãy bỏ rác qua máy để dashboard tạo biểu đồ và lời khuyên chính xác hơn.", severity: "info", created_at: generatedAt, route: "/user/dashboard", action_label: "Xem tổng quan" });
  if (analytics.device_status.status !== "online") notifications.push({ id: "device-status", title: "Thiết bị cần kiểm tra", message: analytics.device_status.message, severity: "warning", created_at: generatedAt, route: "/user/device", action_label: "Xem thiết bị" });
  analytics.bins.filter((item) => item.percent >= 75).forEach((item) => notifications.push({ id: `bin-${item.bin_index}`, title: `Thùng ${item.bin_index} đang đầy ${item.percent}%`, message: `${item.label} cần được xử lý sớm để tránh tràn thùng.`, severity: item.percent >= 95 ? "danger" : "warning", created_at: generatedAt, route: "/user/device", action_label: "Xem thùng" }));
  const recyclable = routeCount(analytics, "I");
  const activeDays = analytics.daily.filter((item) => item.total > 0).length;
  return {
    generated_at: generatedAt,
    range_days: rangeDays,
    notifications: notifications.slice(0, 6),
    challenges: [
      { id: "recycle-10", title: "10 lượt tái chế sạch", description: "Tích lũy các món thuộc nhóm tái chế trong kỳ này.", progress: Math.min(recyclable, 10), target: 10, unit: "lượt", completed: recyclable >= 10, reward_label: "Huy hiệu Tái chế" },
      { id: "seven-day-streak", title: "Duy trì 7 ngày có dữ liệu", description: "Mỗi ngày ghi nhận ít nhất một lượt phân loại.", progress: Math.min(activeDays, 7), target: 7, unit: "ngày", completed: activeDays >= 7, reward_label: "Chuỗi xanh" }
    ],
    leaderboard: [
      { rank: 1, label: "Bạn", score: analytics.eco_score.score, detail: `${analytics.total} lượt trong ${rangeDays} ngày`, current_user: true },
      { rank: 2, label: "Mục tiêu xanh", score: 80, detail: "Mốc nên đạt", current_user: false }
    ].sort((a, b) => b.score - a.score).map((item, index) => ({ ...item, rank: index + 1 })),
    community_cards: analytics.total ? [{ id: "eco-score", title: "Eco Score của tôi", message: `Bạn đang đạt ${analytics.eco_score.score}/100 điểm trong kỳ này.`, metric: `${analytics.eco_score.score}/100`, share_text: "Tôi đang theo dõi thói quen phân loại rác với Trash Sorter Pro.", tone: analytics.eco_score.score >= 70 ? "success" : "warning" }] : [{ id: "welcome", title: "Bắt đầu nhật ký xanh", message: "Khi có dữ liệu, Eco-Share sẽ tạo thẻ chia sẻ thành tích.", metric: "0 lượt", share_text: "", tone: "neutral" }],
    quick_actions: [{ label: "Xem báo cáo", route: "/user/reports" }, { label: "Hỏi EcoPet", route: "/user/ecopet" }, { label: "Kiểm tra thiết bị", route: "/user/device" }]
  };
}

export async function cloudUserDashboardSummary(identity: CloudAuthIdentity, rangeDays: AnalyticsRangeDays) {
  const [analytics, history, binMap, alerts, schedules] = await Promise.all([
    cloudUserAnalytics(identity, rangeDays),
    cloudUserHistory(identity, { limit: 24 }),
    cloudBinMap(identity, false),
    cloudAlerts(identity, false),
    cloudSchedules(identity)
  ]);
  const deviceStatus = { ...analytics.device_status, bins: analytics.bins };
  const device: UserDevice = {
    generated_at: new Date().toISOString(),
    device_status: deviceStatus,
    bins: analytics.bins,
    recent_activity: history.rows.slice(0, 8),
    owner_username: identity.username
  };
  return {
    analytics,
    history,
    device,
    report: buildUserReport(analytics, rangeDays),
    experience: buildUserExperience(analytics, rangeDays),
    bin_map: binMap,
    alerts,
    schedules
  };
}

export async function cloudUserAdvisor(identity: CloudAuthIdentity, rangeDays: AnalyticsRangeDays): Promise<UserAdvisorResponse> {
  const analytics = await cloudUserAnalytics(identity, rangeDays);
  const primary = analytics.insights[0];
  return {
    generated_at: new Date().toISOString(),
    available: true,
    provider: "supabase-cloud",
    model: "cloud-analytics-advisor",
    profile: "trash_sorter_user",
    range_days: rangeDays,
    message: primary?.message ?? "Chưa có dữ liệu phân loại trong khoảng này. Hãy sử dụng thiết bị để EcoPet đưa ra gợi ý chính xác hơn.",
    local_insights: analytics.insights,
    knowledge_used: ["user-history", "bin-status"],
    safety_notice: "Gợi ý được tạo từ dữ liệu thuộc chính tài khoản của bạn."
  };
}

export async function cloudUserHistoryCsv(identity: CloudAuthIdentity, rangeDays: AnalyticsRangeDays) {
  const result = await cloudOperationsPool().query<HistoryRow>(
    `select id, ts, cls_name, confidence, route_label, bin_index, uart_command,
            ack_status, device_id, image_available
       from public.history
      where owner_username = $1
        and ts >= current_date - ($2::int - 1) * interval '1 day'
      order by ts desc, id desc`,
    [identity.username, rangeDays]
  );
  const lines = [CSV_FIELDS.join(",")];
  for (const row of result.rows) {
    const item = historyItem(row);
    lines.push([item.id, item.ts, item.cls_name, item.confidence, item.category, item.route_label ?? "", item.bin_index ?? "", item.ack_status ?? "", item.device_id ?? ""].map(csvCell).join(","));
  }
  return `${lines.join("\r\n")}\r\n`;
}

export function buildAnalytics(rows: HistoryRow[], deviceStatus: DeviceStatus, bins: BinFullness[], rangeDays: AnalyticsRangeDays): UserAnalytics {
  const now = new Date();
  const today = dateKey(now);
  const currentStart = addDays(now, -(rangeDays - 1));
  const previousStart = addDays(currentStart, -rangeDays);
  const current = rows.filter((row) => inDateRange(row.ts, currentStart, now));
  const previous = rows.filter((row) => inDateRange(row.ts, previousStart, addDays(currentStart, -1)));
  const routeTotals = routeSummary(current);
  const averageConfidence = current.length ? round1(current.reduce((sum, row) => sum + Number(row.confidence || 0) * 100, 0) / current.length) : 0;
  const daily = dailySeries(current, currentStart, now);
  const activeDays = daily.filter((item) => item.total > 0).length;
  const rates = Object.fromEntries(routeTotals.map((item) => [item.command, item.percent]));
  const rawScore = 35 + (rates.I ?? 0) * 0.32 + (rates.O ?? 0) * 0.14 + Math.min(100, activeDays / rangeDays * 100) * 0.18 + averageConfidence * 0.08 - (rates.R ?? 0) * 0.18;
  const score = Math.max(0, Math.min(100, Math.round(rawScore)));
  const insights: WellnessInsight[] = current.length ? [] : [{ kind: "empty", title: "Chưa có dữ liệu", message: "Máy chưa ghi nhận rác trong khoảng thời gian này.", severity: "info" }];
  if ((rates.I ?? 0) >= 45) insights.push({ kind: "recycling", title: "Tỷ lệ tái chế tốt", message: "Hãy tiếp tục làm sạch chai, lon và giấy trước khi bỏ.", severity: "info" });
  if ((rates.R ?? 0) >= 55) insights.push({ kind: "single_use", title: "Nhiều rác vô cơ", message: "Có thể giảm đồ dùng một lần trong những ngày tới.", severity: "warning" });
  deviceStatus.bins = bins;
  const counts = classCounts(current);
  return {
    generated_at: now.toISOString(), range_days: rangeDays, total: current.length,
    today_total: current.filter((row) => dateKey(new Date(row.ts)) === today).length,
    seven_day_total: rows.filter((row) => inDateRange(row.ts, addDays(now, -6), now)).length,
    thirty_day_total: rows.filter((row) => inDateRange(row.ts, addDays(now, -29), now)).length,
    average_confidence: averageConfidence,
    eco_score: { score, label: score >= 80 ? "Rất tốt" : score >= 60 ? "Ổn định" : score >= 40 ? "Cần cải thiện" : "Cần theo dõi", recyclable_rate: rates.I ?? 0, inorganic_rate: rates.R ?? 0, organic_rate: rates.O ?? 0, consistency_score: round1(Math.min(100, activeDays / rangeDays * 100)) },
    device_status: deviceStatus, advice: insights, recent_classifications: current.slice(0, 12).map(historyItem),
    comparison: { previous_total: previous.length, delta: current.length - previous.length, delta_percent: previous.length ? round1((current.length - previous.length) / previous.length * 100) : 0 },
    bins, route_totals: routeTotals, top_classes: counts,
    daily, monthly: rangeDays >= 30 ? monthlySeries(current, currentStart, now) : [],
    yesterday: { date: dateKey(addDays(now, -1)), total: daily.at(-2)?.total ?? 0, top_classes: classCounts(current.filter((row) => dateKey(new Date(row.ts)) === dateKey(addDays(now, -1)))).slice(0, 6), route_totals: routeSummary(current.filter((row) => dateKey(new Date(row.ts)) === dateKey(addDays(now, -1)))) },
    insights, advisor_available: false, advisor_model: ""
  };
}

async function scopedDeviceStatus(username: string): Promise<DeviceStatus> {
  const result = await cloudOperationsPool().query<DeviceRow>(`select device_id, device_name, location, owner_username, status, message, last_seen_at from public.devices where owner_username = $1 and coalesce(active::text, '') not in ('0','false','f','no','') order by last_seen_at desc nulls last limit 1`, [username]);
  const row = result.rows[0];
  if (!row) return { device_id: "", device_name: "Chưa được gán thiết bị", location: "", owner_username: username, online: false, status: "offline", message: "Tài khoản chưa được gán thiết bị EcoSort.", last_active_at: null, bins: [] };
  const status = row.status === "online" ? "online" : row.status === "warning" || row.status === "maintenance" ? "warning" : "offline";
  return { device_id: row.device_id, device_name: row.device_name, location: row.location ?? "", owner_username: username, online: status === "online", status, message: row.message ?? "", last_active_at: row.last_seen_at ? new Date(row.last_seen_at).toISOString() : null, bins: [] };
}

async function scopedBins(username: string): Promise<BinFullness[]> {
  const result = await cloudOperationsPool().query<BinRow>(`select b.bin_index, b.label, s.name as station_name, b.fill_percent, b.updated_at from public.bins b join public.bin_stations s on s.station_id = b.station_id where s.assigned_owner_username = $1 and coalesce(b.active::text, '') not in ('0','false','f','no','') order by s.name, b.bin_index`, [username]);
  return result.rows.map((row) => ({ bin_index: Number(row.bin_index), label: `${row.station_name} - ${row.label}`, percent: Math.max(0, Math.min(100, Number(row.fill_percent ?? 0))), updated_at: row.updated_at ? new Date(row.updated_at).toISOString() : null, stale: !row.updated_at || Date.now() - new Date(row.updated_at).getTime() > 120_000 }));
}

function historyItem(row: HistoryRow): UserHistoryItem { return { id: Number(row.id), ts: new Date(row.ts).toISOString(), cls_name: row.cls_name, confidence: round3(Number(row.confidence ?? 0)), route_label: row.route_label, bin_index: row.bin_index === null ? null : Number(row.bin_index), category: category(row), ack_status: row.ack_status, device_id: row.device_id, image_available: false }; }
function category(row: HistoryRow): UserHistoryItem["category"] { const command = row.uart_command?.trim().toUpperCase(); if (command === "O" || Number(row.bin_index) === 1) return "organic"; if (command === "I" || Number(row.bin_index) === 3) return "recyclable"; return "inorganic"; }
function routeSummary(rows: HistoryRow[]): UserRouteTotal[] { const commands = [{ command: "O" as const, route_label: "Hữu cơ", bin_index: 1 }, { command: "R" as const, route_label: "Vô cơ", bin_index: 2 }, { command: "I" as const, route_label: "Tái chế", bin_index: 3 }]; return commands.map((base) => { const count = rows.filter((row) => category(row) === (base.command === "O" ? "organic" : base.command === "I" ? "recyclable" : "inorganic")).length; return { ...base, count, percent: percent(count, rows.length) }; }); }
function classCounts(rows: HistoryRow[]): WasteClassCount[] { const map = new Map<string, HistoryRow[]>(); rows.forEach((row) => map.set(row.cls_name, [...(map.get(row.cls_name) ?? []), row])); return [...map.entries()].map(([cls_name, items]) => ({ cls_name, count: items.length, bin_index: items[0].bin_index === null ? null : Number(items[0].bin_index), route_label: items[0].route_label, percent: percent(items.length, rows.length) })).sort((a, b) => b.count - a.count).slice(0, 10); }
function dailySeries(rows: HistoryRow[], start: Date, end: Date) { const out = []; for (let day = startOfDay(start); day <= end; day = addDays(day, 1)) { const items = rows.filter((row) => dateKey(new Date(row.ts)) === dateKey(day)); out.push({ date: dateKey(day), total: items.length, organic: items.filter((row) => category(row) === "organic").length, inorganic: items.filter((row) => category(row) === "inorganic").length, recyclable: items.filter((row) => category(row) === "recyclable").length }); } return out; }
function monthlySeries(rows: HistoryRow[], start: Date, end: Date) { const out = []; const cursor = new Date(start.getFullYear(), start.getMonth(), 1); while (cursor <= end) { const key = dateKey(cursor).slice(0, 7); const items = rows.filter((row) => dateKey(new Date(row.ts)).startsWith(key)); out.push({ month: key, total: items.length, organic: items.filter((row) => category(row) === "organic").length, inorganic: items.filter((row) => category(row) === "inorganic").length, recyclable: items.filter((row) => category(row) === "recyclable").length }); cursor.setMonth(cursor.getMonth() + 1); } return out; }
function routeCount(analytics: UserAnalytics, command: "O" | "R" | "I") { return analytics.route_totals.find((item) => item.command === command)?.count ?? 0; }
function inDateRange(value: Date | string, start: Date, end: Date) { const date = new Date(value); return date >= startOfDay(start) && date <= endOfDay(end); }
function startOfDay(value: Date) { return new Date(value.getFullYear(), value.getMonth(), value.getDate()); }
function endOfDay(value: Date) { return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 23, 59, 59, 999); }
function addDays(value: Date, days: number) { const date = new Date(value); date.setDate(date.getDate() + days); return date; }
function dateKey(value: Date) { const year = value.getFullYear(); return `${year}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`; }
function percent(count: number, total: number) { return total ? round1(count / total * 100) : 0; }
function round1(value: number) { return Math.round(value * 10) / 10; }
function round3(value: number) { return Math.round(value * 1000) / 1000; }
function csvCell(value: unknown) { const text = String(value ?? ""); return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text; }
