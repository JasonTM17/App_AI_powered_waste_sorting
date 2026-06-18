import {
  AgentApiError,
  CLOUD_API_URL,
  agentResponseErrorDetail,
  type AiChatResponse,
  type AuthRole
} from "@/lib/agent";

type StreamMeta = {
  quota_limit?: number;
  quota_used?: number;
  quota_remaining?: number;
  quota_reset_at?: string;
  quota_exceeded?: boolean;
};

type StreamOptions = {
  message: string;
  onProgress: (response: AiChatResponse) => void;
  path: "/api/admin/chat" | "/api/user/chat";
  role: AuthRole;
  signal: AbortSignal;
  token: string;
};

export async function streamCloudChat(options: StreamOptions) {
  const response = await fetch(`${CLOUD_API_URL}${options.path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${options.token}`,
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ message: options.message }),
    cache: "no-store",
    signal: options.signal
  });
  if (!response.ok || !response.body) {
    const detail = await agentResponseErrorDetail(response);
    throw new AgentApiError(detail || `Chat API failed (${response.status})`, response.status);
  }
  if ((response.headers.get("content-type") ?? "").includes("application/json")) {
    const completed = await response.json() as AiChatResponse;
    options.onProgress(completed);
    return completed;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let answer = "";
  let meta: StreamMeta = {};
  let completed: AiChatResponse | null = null;
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split(/\r?\n\r?\n/);
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const parsed = parseEvent(frame);
      if (!parsed) continue;
      if (parsed.event === "meta") {
        meta = parsed.data as StreamMeta;
      } else if (parsed.event === "delta") {
        const text = String((parsed.data as { text?: unknown }).text ?? "");
        if (!text) continue;
        answer += text;
        options.onProgress(partialResponse(options.role, answer, meta));
      } else if (parsed.event === "done") {
        completed = parsed.data as AiChatResponse;
      }
    }
    if (done) break;
  }
  if (!completed) throw new AgentApiError("Chat stream ended before completion", 0);
  return completed;
}

function parseEvent(frame: string) {
  if (!frame || frame.startsWith(":")) return null;
  let event = "message";
  const data: string[] = [];
  for (const line of frame.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trim());
  }
  if (!data.length) return null;
  try {
    return { event, data: JSON.parse(data.join("\n")) as unknown };
  } catch {
    return null;
  }
}

function partialResponse(role: AuthRole, message: string, meta: StreamMeta): AiChatResponse {
  return {
    generated_at: new Date().toISOString(),
    available: true,
    provider: "deepseek",
    model: "deepseek-v4-flash",
    answer_source: "deepseek",
    latency_ms: 0,
    role,
    profile: role === "admin" ? "trash_sorter_admin" : "trash_sorter_user",
    message,
    quick_prompts: role === "admin"
      ? ["Tóm tắt trạng thái cloud", "Kiểm tra camera", "Kiểm tra bridge"]
      : ["Xem Eco Score", "Xem bản đồ thùng", "Báo lỗi thiết bị"],
    knowledge_used: [],
    safety_notice: "Dữ liệu được giới hạn theo quyền tài khoản.",
    ...meta
  };
}
