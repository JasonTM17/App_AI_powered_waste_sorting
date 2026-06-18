import type { AiChatResponse } from "@/lib/agent";
import type { CloudAuthIdentity, CloudAuthRole } from "@/lib/server/cloud-auth";
import { askCloudDeepSeek, CLOUD_CHAT_MODEL, deepSeekIsConfigured } from "@/lib/server/cloud-chat-ai";
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
