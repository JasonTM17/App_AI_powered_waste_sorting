"use client";

import {
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  CalendarCheck,
  CheckCircle2,
  FileDown,
  HeartPulse,
  History,
  Home,
  MapPin,
  Server,
  Trophy,
  UserRound,
  Users,
  type LucideIcon
} from "lucide-react";

import { AccountControl } from "@/components/account-control";
import { TrashSorterLogo } from "@/components/brand/trash-sorter-logo";
import { RoleChatbotLauncher } from "@/components/chat/role-chatbot-launcher";
import { RangeSelector } from "@/components/user-dashboard/range-selector";
import type { UserDashboardPanelProps, UserView } from "@/components/user-dashboard/user-dashboard-types";
import { UserHeroSummary } from "@/components/user-dashboard/user-hero-summary";
import { UserRouteContent } from "@/components/user-dashboard/user-route-content";

const userNav: Array<{ id: UserView; href: string; label: string; icon: LucideIcon }> = [
  { id: "dashboard", href: "/user/dashboard", label: "Tổng quan", icon: Home },
  { id: "analytics", href: "/user/analytics", label: "Phân tích", icon: BarChart3 },
  { id: "map", href: "/user/map", label: "Bản đồ thùng", icon: MapPin },
  { id: "alerts", href: "/user/alerts", label: "Cảnh báo", icon: AlertTriangle },
  { id: "schedule", href: "/user/schedule", label: "Lịch thu gom", icon: CalendarCheck },
  { id: "collect", href: "/user/collect", label: "Đã thu gom", icon: CheckCircle2 },
  { id: "report-issue", href: "/user/report-issue", label: "Báo lỗi", icon: Bell },
  { id: "history", href: "/user/history", label: "Lịch sử", icon: History },
  { id: "device", href: "/user/device", label: "Thiết bị", icon: Server },
  { id: "ecopet", href: "/user/ecopet", label: "EcoPet AI", icon: Bot },
  { id: "advice", href: "/user/advice", label: "Lời khuyên", icon: HeartPulse },
  { id: "reports", href: "/user/reports", label: "Báo cáo", icon: FileDown },
  { id: "notifications", href: "/user/notifications", label: "Thông báo", icon: Bell },
  { id: "community", href: "/user/community", label: "Eco-Share", icon: Users },
  { id: "leaderboard", href: "/user/leaderboard", label: "Thử thách", icon: Trophy },
  { id: "account", href: "/user/account", label: "Tài khoản", icon: UserRound }
];

export function UserDashboardPanel(props: UserDashboardPanelProps) {
  const { agentError, analytics, auth, busy, chatAnswer, chatBusy, chatQuestion, notice, rangeDays, view } = props;
  const primaryNav = userNav.slice(0, 5);
  const secondaryNav = userNav.slice(5);
  return (
    <div className="app-shell user-shell polished-user-shell">
      <aside className="sidebar user-sidebar">
        <div className="brand">
          <div className="brand-mark">
            <TrashSorterLogo />
          </div>
          <div>
            <strong>Trash Sorter Pro</strong>
            <span>EcoSort AI</span>
          </div>
        </div>
        <nav className="nav-list user-nav-list" aria-label="User navigation">
          <UserNavGroup items={primaryNav} view={view} onViewChange={props.onViewChange} />
          <div className="user-nav-divider" />
          <UserNavGroup items={secondaryNav} view={view} onViewChange={props.onViewChange} />
        </nav>
        <div className="agent-card user-agent-card">
          <span className="eyebrow">Hỗ trợ</span>
          <strong>Thiết bị EcoSort</strong>
          <div className={agentError ? "system-pill offline" : "system-pill"}>
            <span className="pulse-dot" />
            <span>{agentError ? "Cần tải lại dữ liệu" : "Đang đồng bộ"}</span>
          </div>
        </div>
      </aside>

      <main className="workspace user-workspace">
        <header className="topbar user-topbar">
          <strong className="stitch-topbar-title">Trash Sorter Pro</strong>
          <div className="stitch-user-search" aria-label="Trạng thái dữ liệu người dùng">
            <span>Dữ liệu từ thiết bị EcoSort local</span>
          </div>
          <AccountControl auth={auth} busy={busy} onLogout={props.onLogout} />
        </header>

        <UserHeroSummary analytics={analytics} auth={auth} busy={busy} />

        {view !== "account" ? (
          <div className="user-range-row">
            <div>
              <span className="eyebrow">Khoảng thời gian</span>
              <strong>Xem theo ngày và tháng</strong>
            </div>
            <RangeSelector rangeDays={rangeDays} onRangeChange={props.onRangeChange} />
          </div>
        ) : null}

        {agentError ? <div className="alert">Dữ liệu chưa sẵn sàng: {agentError}</div> : null}
        {notice && !agentError ? <div className="success">{notice}</div> : null}

        <section className="content-grid user-dashboard-grid">
          <UserRouteContent {...props} />
        </section>

        {props.chatbotEnabled ? (
          <RoleChatbotLauncher
            answer={chatAnswer}
            busy={chatBusy}
            defaultOpen={view === "ecopet"}
            label="EcoPet"
            placeholder="Hỏi EcoPet..."
            question={chatQuestion}
            role="user"
            statusText="EcoPet sẵn sàng đồng hành cùng thói quen phân loại rác của bạn."
            title="EcoPet"
            onAsk={props.onChatRequest}
            onQuestionChange={props.onChatQuestionChange}
          />
        ) : null}
      </main>
    </div>
  );
}

function UserNavGroup({
  items,
  onViewChange,
  view
}: {
  items: Array<{ id: UserView; href: string; label: string; icon: LucideIcon }>;
  view: UserView;
  onViewChange: (value: UserView) => void;
}) {
  return (
    <>
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <a
            className={view === item.id ? "nav-item active" : "nav-item"}
            href={item.href}
            key={item.id}
            onClick={(event) => {
              event.preventDefault();
              window.history.pushState(null, "", item.href);
              onViewChange(item.id);
            }}
          >
            <Icon size={18} />
            <span>{item.label}</span>
          </a>
        );
      })}
    </>
  );
}
