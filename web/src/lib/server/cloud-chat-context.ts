import type { QueryResultRow } from "pg";

import { cloudAuthPool, type CloudAuthIdentity } from "@/lib/server/cloud-auth";
import { cloudAlerts, cloudBinMap, cloudSchedules } from "@/lib/server/cloud-operations";

export const USER_CHAT_MONTHLY_LIMIT = 36;

export type CloudChatQuota = {
  quota_limit: number;
  quota_used: number;
  quota_remaining: number;
  quota_reset_at: string;
  quota_exceeded: boolean;
};

type KnowledgeRow = QueryResultRow & {
  id: string;
  title: string;
  keywords: string[] | null;
  body: string;
};

export async function consumeCloudChatQuota(accountId: number): Promise<CloudChatQuota> {
  const period = new Date().toISOString().slice(0, 7);
  const result = await cloudAuthPool().query<{ used: number | string }>(
    `insert into chat_usage (account_id, period, used, updated_at)
     values ($1, $2, 1, $3)
     on conflict (account_id, period) do update
       set used = chat_usage.used + 1, updated_at = excluded.updated_at
       where chat_usage.used < $4
     returning used`,
    [accountId, period, new Date().toISOString(), USER_CHAT_MONTHLY_LIMIT]
  );
  const consumed = result.rows[0];
  const used = consumed ? Number(consumed.used) : await currentUsage(accountId, period);
  return {
    quota_limit: USER_CHAT_MONTHLY_LIMIT,
    quota_used: Math.min(USER_CHAT_MONTHLY_LIMIT, used),
    quota_remaining: Math.max(0, USER_CHAT_MONTHLY_LIMIT - used),
    quota_reset_at: quotaResetAt(),
    quota_exceeded: !consumed
  };
}

export async function buildCloudChatContext(identity: CloudAuthIdentity, message: string) {
  const intent = chatContextIntent(message);
  const [history, map, alerts, schedules, knowledge] = await Promise.all([
    intent.history ? safe(() => historyContext(identity)) : Promise.resolve({ requested: false }),
    intent.map ? safe(() => cloudBinMap(identity, false).then(compactMap)) : Promise.resolve({ requested: false }),
    intent.alerts ? safe(() => cloudAlerts(identity, false).then(compactAlerts)) : Promise.resolve({ requested: false }),
    intent.schedules ? safe(() => cloudSchedules(identity).then(compactSchedules)) : Promise.resolve({ requested: false }),
    safe(() => knowledgeContext(identity.role, message))
  ]);
  const snippets = Array.isArray(knowledge) ? knowledge : [];
  return {
    context: {
      scope: identity.role === "admin" ? "admin_all_cloud_data" : "user_owned_cloud_data",
      account: { username: identity.username, display_name: identity.display_name, role: identity.role },
      history,
      operations_map: map,
      alerts,
      schedules,
      knowledge: snippets
    },
    knowledgeUsed: snippets.map((item) => item.title)
  };
}

async function historyContext(identity: CloudAuthIdentity) {
  const owner = identity.role === "admin" ? "" : identity.username;
  const [summary, classes] = await Promise.all([
    cloudAuthPool().query(
      `select count(*) filter (where ts >= current_date)::int as today_total,
              count(*) filter (where ts >= current_date - interval '29 days')::int as thirty_day_total,
              round(avg(confidence) filter (where ts >= current_date - interval '29 days')::numeric, 4) as average_confidence
         from public.history where ($1::text = '' or owner_username = $1)`,
      [owner]
    ),
    cloudAuthPool().query(
      `select cls_name, count(*)::int as count from public.history
        where ($1::text = '' or owner_username = $1)
          and ts >= current_date - interval '29 days'
        group by cls_name order by count(*) desc, cls_name limit 8`,
      [owner]
    )
  ]);
  return { available: true, ...summary.rows[0], top_classes: classes.rows };
}

async function knowledgeContext(role: "admin" | "user", message: string) {
  const result = await cloudAuthPool().query<KnowledgeRow>(
    `select id, title, keywords, body from public.knowledge_entries
      where enabled = true and $1::text = any(roles)
      order by updated_at desc limit 30`,
    [role]
  );
  const terms = normalizedTerms(message);
  return result.rows
    .map((row) => ({ ...row, score: scoreKnowledge(row, terms) }))
    .filter((row) => row.score > 0 || terms.size === 0)
    .sort((left, right) => right.score - left.score)
    .slice(0, 4)
    .map((row) => ({ id: row.id, title: row.title, text: row.body.slice(0, 450) }));
}

function chatContextIntent(message: string) {
  const normalized = normalizeForMatch(message);
  const map = /ban do|map|thung|day|diem rac|tram|vi tri/.test(normalized);
  const schedules = /lich|thu gom|collection|sap toi/.test(normalized);
  const operations = /camera|uart|usb|bridge|thiet bi|van hanh|trang thai|canh bao/.test(normalized);
  const history = /lich su|eco score|phan loai|hom nay|thang|tuan|bieu do|tai che/.test(normalized)
    || (!map && !schedules && !operations);
  return { history, map: map || operations, alerts: map || operations, schedules: schedules || operations };
}

function compactMap(value: unknown) {
  const map = value as { stations?: Array<Record<string, unknown>> };
  return {
    stations: (map.stations ?? []).slice(0, 12).map((station) => ({
      station_id: station.station_id,
      name: station.name,
      area: station.area,
      owner_username: station.owner_username,
      open_alert_total: station.open_alert_total,
      bins: Array.isArray(station.bins)
        ? station.bins.slice(0, 3).map((bin) => {
            const item = bin as Record<string, unknown>;
            return { bin_id: item.bin_id, label: item.label, fill_percent: item.fill_percent, status: item.status };
          })
        : []
    }))
  };
}

function compactAlerts(value: unknown) {
  const alerts = value as { alerts?: Array<Record<string, unknown>> };
  return {
    alerts: (alerts.alerts ?? []).slice(0, 8).map((alert) => ({
      alert_id: alert.alert_id,
      station_id: alert.station_id,
      severity: alert.severity,
      title: alert.title,
      status: alert.status,
      created_at: alert.created_at
    }))
  };
}

function compactSchedules(value: unknown) {
  const schedules = value as { schedules?: Array<Record<string, unknown>> };
  return {
    schedules: (schedules.schedules ?? []).slice(0, 6).map((schedule) => ({
      schedule_id: schedule.schedule_id,
      station_name: schedule.station_name,
      scheduled_date: schedule.scheduled_date,
      status: schedule.status
    }))
  };
}

async function currentUsage(accountId: number, period: string) {
  const result = await cloudAuthPool().query<{ used: number | string }>(
    "select used from chat_usage where account_id = $1 and period = $2 limit 1",
    [accountId, period]
  );
  return Number(result.rows[0]?.used ?? USER_CHAT_MONTHLY_LIMIT);
}

async function safe<T>(operation: () => Promise<T>): Promise<T | { available: false }> {
  try {
    return await operation();
  } catch {
    return { available: false };
  }
}

function normalizedTerms(value: string) {
  return new Set(value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().split(/[^a-z0-9]+/).filter((term) => term.length >= 3));
}

function normalizeForMatch(value: string) {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").toLowerCase();
}

function scoreKnowledge(row: KnowledgeRow, terms: Set<string>) {
  const haystack = normalizedTerms(`${row.title} ${(row.keywords ?? []).join(" ")} ${row.body}`);
  return [...terms].reduce((score, term) => score + (haystack.has(term) ? 1 : 0), 0);
}

function quotaResetAt() {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1)).toISOString();
}
