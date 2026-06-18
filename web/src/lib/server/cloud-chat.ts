import type { AiChatResponse } from "@/lib/agent";
import type { CloudAuthIdentity, CloudAuthRole } from "@/lib/server/cloud-auth";
import { askCloudDeepSeek, CLOUD_CHAT_MODEL, deepSeekIsConfigured, streamCloudDeepSeek } from "@/lib/server/cloud-chat-ai";
import { buildCloudChatContext, consumeCloudChatQuota, type CloudChatQuota } from "@/lib/server/cloud-chat-context";

const USER_QUICK_PROMPTS = ["Xem Eco Score", "Xem bản đồ thùng", "Báo lỗi thiết bị"];
const ADMIN_QUICK_PROMPTS = ["Tóm tắt trạng thái cloud", "Kiểm tra camera", "Kiểm tra bridge"];
const SAFETY_NOTICE = "EcoPet chỉ dùng dữ liệu đã giới hạn theo quyền tài khoản; thao tác phần cứng của Admin đi qua bridge được bảo vệ.";
const UNSAFE_INSTRUCTION_PATTERNS = [
  /\b(ignore|disregard|forget|bypass|override)\b.{0,120}\b(previous|above|system|developer|instruction|rules?)\b/gi,
  /\b(reveal|show|print|dump|exfiltrate|leak)\b.{0,120}\b(system prompt|password|token|secret|api key|raw context|raw log)\b/gi,
  /\b(system prompt|developer message|api key|session token|password hash|raw context|raw log)\b/gi
];

export class CloudChatInputError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "CloudChatInputError";
  }
}

export function parseCloudChatMessage(value: unknown) {
  if (typeof value !== "string") throw new CloudChatInputError("Tin nhắn phải là chuỗi văn bản.");
  let message = value.replace(/\0/g, " ").trim();
  if (!message) throw new CloudChatInputError("Vui lòng nhập câu hỏi.");
  if (message.length > 700) throw new CloudChatInputError("Câu hỏi không được vượt quá 700 ký tự.");
  for (const pattern of UNSAFE_INSTRUCTION_PATTERNS) {
    message = message.replace(pattern, "[đã loại bỏ chỉ dẫn không an toàn]");
  }
  return message;
}

export async function generateCloudChatResponse(
  identity: CloudAuthIdentity,
  rawMessage: unknown,
  startedAt = Date.now()
): Promise<AiChatResponse> {
  const message = parseCloudChatMessage(rawMessage);
  const quota = identity.role === "user" ? await consumeCloudChatQuota(identity.account_id) : undefined;
  if (quota?.quota_exceeded) return quotaResponse(identity.role, quota, startedAt);

  const { context, knowledgeUsed } = await buildCloudChatContext(identity, message);
  if (!deepSeekIsConfigured()) return fallbackResponse(identity.role, message, startedAt, quota, knowledgeUsed);
  try {
    const answer = await askCloudDeepSeek(identity.role, message, context);
    return baseResponse(identity.role, startedAt, {
      available: true,
      provider: "deepseek",
      model: CLOUD_CHAT_MODEL,
      answer_source: "deepseek",
      message: answer,
      knowledge_used: knowledgeUsed,
      ...quota
    });
  } catch {
    return fallbackResponse(identity.role, message, startedAt, quota, knowledgeUsed);
  }
}

export async function createCloudChatStreamResponse(
  identity: CloudAuthIdentity,
  rawMessage: unknown,
  startedAt = Date.now(),
  signal?: AbortSignal
) {
  const message = parseCloudChatMessage(rawMessage);
  const quotaStartedAt = Date.now();
  const quota = identity.role === "user" ? await consumeCloudChatQuota(identity.account_id) : undefined;
  const quotaDuration = Date.now() - quotaStartedAt;
  const contextStartedAt = Date.now();
  const prepared = quota?.quota_exceeded
    ? { context: {}, knowledgeUsed: [] as string[] }
    : await buildCloudChatContext(identity, message);
  const contextDuration = Date.now() - contextStartedAt;
  const requestId = crypto.randomUUID();
  const encoder = new TextEncoder();
  let streamClosed = false;
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      const send = (event: string, data: unknown) => {
        if (streamClosed) return;
        try {
          controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`));
        } catch {
          streamClosed = true;
        }
      };
      heartbeat = setInterval(() => {
        if (streamClosed) return;
        try {
          controller.enqueue(encoder.encode(": heartbeat\n\n"));
        } catch {
          streamClosed = true;
        }
      }, 10_000);
      const finish = () => {
        if (streamClosed) return;
        streamClosed = true;
        if (heartbeat) clearInterval(heartbeat);
        try {
          controller.close();
        } catch {
          // The browser may have cancelled the stream already.
        }
      };
      void (async () => {
        send("meta", { request_id: requestId, ...quota });
        if (quota?.quota_exceeded) {
          const response = quotaResponse(identity.role, quota, startedAt);
          send("delta", { text: response.message });
          send("done", response);
          finish();
          return;
        }
        if (!deepSeekIsConfigured()) {
          const response = fallbackResponse(identity.role, message, startedAt, quota, prepared.knowledgeUsed);
          send("delta", { text: response.message });
          send("done", response);
          finish();
          return;
        }
        let streamedText = "";
        try {
          const answer = await streamCloudDeepSeek(
            identity.role,
            message,
            prepared.context,
            (text) => {
              streamedText += text;
              send("delta", { text });
            },
            signal
          );
          send("done", baseResponse(identity.role, startedAt, {
            available: true,
            provider: "deepseek",
            model: CLOUD_CHAT_MODEL,
            answer_source: "deepseek",
            message: answer,
            knowledge_used: prepared.knowledgeUsed,
            ...quota
          }));
        } catch {
          const response = fallbackResponse(identity.role, message, startedAt, quota, prepared.knowledgeUsed);
          send("error", {
            code: signal?.aborted ? "request_cancelled" : "provider_unavailable",
            message: signal?.aborted ? "Yêu cầu đã được hủy." : "AI phản hồi chậm, đang dùng câu trả lời an toàn."
          });
          if (!streamedText) send("delta", { text: response.message });
          send("done", response);
        } finally {
          finish();
        }
      })().catch(() => finish());
    },
    cancel() {
      streamClosed = true;
      if (heartbeat) clearInterval(heartbeat);
    }
  });
  return new Response(body, {
    headers: {
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "Content-Type": "text/event-stream; charset=utf-8",
      "Server-Timing": `quota;dur=${quotaDuration}, context;dur=${contextDuration}`,
      "X-Accel-Buffering": "no"
    }
  });
}

function fallbackResponse(
  role: CloudAuthRole,
  message: string,
  startedAt: number,
  quota?: CloudChatQuota,
  knowledgeUsed: string[] = []
) {
  const hardwareQuestion = /camera|uart|usb|phần cứng|phan cung|huấn luyện|huan luyen/i.test(message);
  const mapQuestion = /thùng|thung|rác|rac|đầy|day|bản đồ|ban do|map|cảnh báo|canh bao/i.test(message);
  let answer = role === "user"
    ? "EcoPet đang tạm gián đoạn kết nối AI. Mình vẫn ở đây với bạn; bạn có thể xem Eco Score, lịch sử và bản đồ, rồi thử hỏi lại sau ít phút nhé."
    : "Trợ lý AI đang tạm gián đoạn. Dữ liệu vận hành vẫn an toàn; Admin có thể kiểm tra lại cấu hình AI và thử lại sau ít phút.";
  if (hardwareQuestion) {
    answer = role === "user"
      ? "Bạn không có quyền điều khiển camera hoặc phần cứng. Nếu thiết bị có vấn đề, hãy dùng mục Báo lỗi thiết bị để Admin kiểm tra an toàn."
      : "Vercel không mở USB trực tiếp. Admin hãy kiểm tra local agent, tunnel HTTPS và hardware bridge trước khi vận hành camera hoặc huấn luyện.";
  } else if (mapQuestion) {
    answer = "AI đang tạm gián đoạn nên mình chưa kết luận trạng thái thùng. Hãy xem Bản đồ và Cảnh báo để đọc dữ liệu Supabase mới nhất, tránh suy đoán khi dữ liệu chưa đủ.";
  }
  return baseResponse(role, startedAt, {
    available: false,
    provider: "vercel-cloud",
    model: "cloud-safe-fallback",
    answer_source: "local",
    message: answer,
    knowledge_used: knowledgeUsed,
    ...quota
  });
}

function quotaResponse(role: CloudAuthRole, quota: CloudChatQuota, startedAt: number) {
  return baseResponse(role, startedAt, {
    available: false,
    provider: "vercel-cloud",
    model: CLOUD_CHAT_MODEL,
    answer_source: "local",
    message: "Bạn đã dùng hết 36 lượt hỏi EcoPet trong tháng này. EcoPet sẽ mở lại lượt hỏi vào đầu tháng tới; biểu đồ và lịch sử vẫn hoạt động bình thường.",
    knowledge_used: [],
    ...quota
  });
}

function baseResponse(
  role: CloudAuthRole,
  startedAt: number,
  values: Pick<AiChatResponse, "available" | "provider" | "model" | "answer_source" | "message" | "knowledge_used"> & Partial<CloudChatQuota>
): AiChatResponse {
  return {
    generated_at: new Date().toISOString(),
    latency_ms: Math.max(0, Date.now() - startedAt),
    role,
    profile: role === "admin" ? "trash_sorter_admin" : "trash_sorter_user",
    quick_prompts: role === "admin" ? ADMIN_QUICK_PROMPTS : USER_QUICK_PROMPTS,
    safety_notice: SAFETY_NOTICE,
    ...values
  };
}
