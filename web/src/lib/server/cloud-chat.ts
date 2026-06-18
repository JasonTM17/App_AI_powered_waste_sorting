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
  const bridgeUrl = process.env.NEXT_PUBLIC_AGENT_URL?.trim() || "http://localhost:8765";
  const isHardwareQuestion = /camera|uart|usb|phan cung|phần cứng|máy|may|trạng thái|tinh trang|status/i.test(message);
  const isFullnessQuestion = /thung|thùng|rac|rác|day|đầy|95|map|ban do|bản đồ/i.test(message);

  const cloudLine =
    "Cloud đang hoạt động: đăng nhập Vercel/Supabase đã sẵn sàng và phiên của bạn hợp lệ.";
  const bridgeLine =
    `Phần camera, UART và cảm biến vẫn phải đi qua hardware bridge tại ${bridgeUrl}. ` +
    "Nếu production còn báo offline, hãy bảo đảm local agent đang chạy, URL này truy cập được từ trình duyệt, và CORS cho phép domain Vercel.";
  const userGuardLine =
    role === "user"
      ? "Role User chỉ xem dashboard, bản đồ, cảnh báo, lịch thu gom và lịch sử của chính mình; User không có quyền camera, dataset, huấn luyện, model, logs hay setting."
      : "Role Admin có quyền vận hành camera, dataset, huấn luyện và cấu hình khi hardware bridge đang online.";

  let answer = `${cloudLine}\n\n${bridgeLine}\n\n${userGuardLine}`;
  if (isHardwareQuestion) {
    answer =
      `${cloudLine}\n\nMình chưa đọc trực tiếp được camera/UART từ Vercel vì phần cứng nằm trên máy local. ` +
      bridgeLine +
      `\n\n${userGuardLine}`;
  } else if (isFullnessQuestion) {
    answer =
      `${cloudLine}\n\nLuồng thùng rác đầy vẫn là: phần cứng gửi mức đầy >= 95%, local agent cập nhật bin fullness, rồi UI hiển thị “Đã đầy” trên popup bản đồ và cảnh báo. ` +
      `Trên cloud, dữ liệu này cần được bridge đồng bộ lên Supabase để mọi máy đều thấy cùng trạng thái.\n\n${bridgeLine}`;
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
        ? ["Tóm tắt trạng thái cloud", "Kiểm tra camera", "Kiểm tra cấu hình bridge"]
        : ["Xem Eco Score", "Xem bản đồ thùng", "Báo lỗi thiết bị"],
    knowledge_used: ["cloud-auth", "hardware-bridge", "rbac"],
    safety_notice:
      "Phản hồi cloud không truy cập trực tiếp camera/UART. Các thao tác phần cứng chỉ chạy qua bridge được cấu hình."
  };
}
