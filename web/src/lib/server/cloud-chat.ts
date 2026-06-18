import type { CloudAuthRole } from "@/lib/server/cloud-auth";

type CloudChatResponse = {
  generated_at: string;
  available: boolean;
  provider: string;
  model: string;
  answer_source: "local" | "deepseek" | "hybrid";
  latency_ms: number;
  role: CloudAuthRole;
  profile: string;
  message: string;
  quick_prompts: string[];
  knowledge_used: string[];
  safety_notice: string;
};

export function buildCloudChatResponse(role: CloudAuthRole, rawMessage: string, startedAt = Date.now()): CloudChatResponse {
  const message = rawMessage.trim();
  const bridgeUrl = process.env.TRASH_SORTER_HARDWARE_BRIDGE_URL?.trim() || "hardware bridge";
  const isHardwareQuestion = /camera|uart|usb|phan cung|phần cứng|may|máy|trang thai|trạng thái|status/i.test(message);
  const isFullnessQuestion = /thung|thùng|rac|rác|day|đầy|95|map|ban do|bản đồ/i.test(message);

  const cloudLine =
    "Cloud dang hoat dong: dang nhap Vercel/Supabase da san sang va phien cua ban hop le.";
  const bridgeLine =
    `Camera va huan luyen cho Admin di qua public hardware bridge HTTPS (${bridgeUrl}) do Vercel proxy va RBAC kiem soat. ` +
    "Neu production bao offline, hay kiem tra local agent, tunnel HTTPS, auth DB chung va bridge secret.";
  const roleLine =
    role === "user"
      ? "Role User chi xem dashboard, ban do, canh bao, lich thu gom va lich su cua chinh minh; User khong co quyen camera, dataset, huan luyen, model, logs hay settings."
      : "Role Admin co quyen xem live camera, bat/tat camera, chup mau camera va chay huan luyen qua bridge khi phan cung online.";

  let answer = `${cloudLine}\n\n${bridgeLine}\n\n${roleLine}`;
  if (isHardwareQuestion) {
    answer =
      `${cloudLine}\n\nVercel khong mo USB truc tiep; Vercel chi proxy admin-only toi hardware bridge dang chay tren may co camera. ` +
      `${bridgeLine}\n\n${roleLine}`;
  } else if (isFullnessQuestion) {
    answer =
      `${cloudLine}\n\nLuong thung rac day van la: phan cung gui muc day >= 95%, local agent cap nhat bin fullness, bridge dong bo len Supabase, ` +
      `roi UI tren moi may hien "Da day" tren ban do va canh bao.\n\n${bridgeLine}`;
  }

  return {
    generated_at: new Date().toISOString(),
    available: true,
    provider: "vercel-cloud",
    model: "cloud-operations-fallback",
    answer_source: "local",
    latency_ms: Math.max(0, Date.now() - startedAt),
    role,
    profile: role === "admin" ? "trash_sorter_admin" : "trash_sorter_user",
    message: answer,
    quick_prompts:
      role === "admin"
        ? ["Tom tat trang thai cloud", "Kiem tra camera", "Kiem tra bridge"]
        : ["Xem Eco Score", "Xem ban do thung", "Bao loi thiet bi"],
    knowledge_used: ["cloud-auth", "hardware-bridge", "rbac"],
    safety_notice:
      "Camera/training public chi danh cho Admin qua bridge allowlist; User va cac route ngoai allowlist bi chan."
  };
}
