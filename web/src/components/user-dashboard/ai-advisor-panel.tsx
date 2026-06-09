"use client";

import { BrainCircuit, Send, ShieldCheck } from "lucide-react";
import { AnalyticsRangeDays, UserAdvisorResponse, UserAnalytics } from "@/lib/agent";

export function AiAdvisorPanel({
  advisor,
  analytics,
  busy,
  question,
  rangeDays,
  onQuestionChange,
  onRequest
}: {
  advisor: UserAdvisorResponse | null;
  analytics: UserAnalytics | null;
  busy: boolean;
  question: string;
  rangeDays: AnalyticsRangeDays;
  onQuestionChange: (value: string) => void;
  onRequest: () => void;
}) {
  const localMessage = analytics?.insights.map((item) => `${item.title}: ${item.message}`).join(" ") || "";
  const quotaText = advisor?.quota_limit
    ? advisor.quota_exceeded || (advisor.quota_remaining ?? 0) <= 0
      ? `Bạn đã dùng hết ${advisor.quota_limit} lượt hỏi trong tháng này.`
      : `Bạn còn ${advisor.quota_remaining}/${advisor.quota_limit} lượt hỏi trong tháng này.`
    : "Bạn có 36 lượt hỏi EcoPet mỗi tháng.";
  return (
    <section className="user-panel advisor-panel compact-advisor-panel">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">EcoPet</span>
          <strong>Gợi ý sức khỏe và thói quen</strong>
        </div>
        <BrainCircuit size={21} />
      </div>
      <div className={analytics?.advisor_available ? "advisor-status online" : "advisor-status"}>
        <ShieldCheck size={16} />
        <span>{analytics?.advisor_available ? "EcoPet đã sẵn sàng đồng hành." : "EcoPet đang dùng gợi ý có sẵn trong ứng dụng."}</span>
      </div>
      <div className="advisor-status user-quota-status">
        <ShieldCheck size={16} />
        <span>{quotaText}</span>
      </div>
      <textarea
        className="advisor-question"
        maxLength={400}
        onChange={(event) => onQuestionChange(event.target.value)}
        placeholder="Ví dụ: Tôi nên giảm đồ nhựa dùng một lần thế nào?"
        value={question}
      />
      <button className="primary-button advisor-button" disabled={busy || !analytics} onClick={onRequest} type="button">
        <Send size={17} />
        <span>{busy ? "Đang tư vấn..." : `Tư vấn từ ${rangeDays} ngày`}</span>
      </button>
      <div className="advisor-answer" aria-live="polite">
        {advisor?.message || localMessage || "Khi có dữ liệu, trợ lý sẽ tóm tắt thói quen và gợi ý cách cải thiện."}
      </div>
      <p className="advisor-disclaimer">
        Lời khuyên chỉ mang tính tham khảo về thói quen sống, không thay thế tư vấn y tế.
      </p>
    </section>
  );
}
