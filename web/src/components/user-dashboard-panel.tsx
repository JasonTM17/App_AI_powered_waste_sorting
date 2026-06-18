"use client";

import {
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  CalendarCheck,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  FileDown,
  HeartPulse,
  History,
  Home,
  MapPin,
  Menu,
  Server,
  Trophy,
  UserRound,
  Users,
  X,
  type LucideIcon
} from "lucide-react";

import { useEffect, useRef, useState } from "react";

import { AccountControl } from "@/components/account-control";
import { TrashSorterLogo } from "@/components/brand/trash-sorter-logo";
import { RoleChatbotLauncher } from "@/components/chat/role-chatbot-launcher";
import { RangeSelector } from "@/components/user-dashboard/range-selector";
import type { UserDashboardPanelProps, UserView } from "@/components/user-dashboard/user-dashboard-types";
import { UserHeroSummary } from "@/components/user-dashboard/user-hero-summary";
import { UserRouteContent } from "@/components/user-dashboard/user-route-content";

type UserNavItem = { id: UserView; href: string; label: string; icon: LucideIcon };

const userNav: UserNavItem[] = [
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

const USER_SIDEBAR_COLLAPSED_KEY = "trash-sorter-user-sidebar-collapsed";
const mobileTaskbarNavIds: UserView[] = ["dashboard", "analytics", "map", "alerts", "account"];

export function UserDashboardPanel(props: UserDashboardPanelProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const mobileDrawerRef = useRef<HTMLDivElement | null>(null);
  const mobileMenuButtonRef = useRef<HTMLButtonElement | null>(null);
  const { agentError, analytics, auth, busy, chatAnswer, chatBusy, chatQuestion, notice, rangeDays, view } = props;
  const primaryNav = userNav.slice(0, 5);
  const secondaryNav = userNav.slice(5);
  const mobileTaskbarNav = mobileTaskbarNavIds
    .map((id) => userNav.find((item) => item.id === id))
    .filter((item): item is UserNavItem => Boolean(item));
  const mobileDrawerNav = userNav.filter((item) => !mobileTaskbarNavIds.includes(item.id));
  const isMapView = view === "map";

  useEffect(() => {
    setIsSidebarCollapsed(window.localStorage.getItem(USER_SIDEBAR_COLLAPSED_KEY) === "1");
  }, []);

  useEffect(() => {
    if (!isMobileNavOpen) {
      return;
    }
    const previousActive = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMobileNavOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    window.setTimeout(() => {
      mobileDrawerRef.current?.querySelector<HTMLAnchorElement | HTMLButtonElement>("a, button")?.focus();
    }, 0);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      if (previousActive && document.contains(previousActive)) {
        previousActive.focus();
      } else {
        mobileMenuButtonRef.current?.focus();
      }
    };
  }, [isMobileNavOpen]);

  useEffect(() => {
    setIsMobileNavOpen(false);
  }, [view]);

  function updateSidebarCollapsed(collapsed: boolean) {
    setIsSidebarCollapsed(collapsed);
    window.localStorage.setItem(USER_SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
  }

  function handleUserViewChange(nextView: UserView) {
    props.onViewChange(nextView);
    setIsMobileNavOpen(false);
  }

  return (
    <div
      className={`app-shell user-shell polished-user-shell ${isSidebarCollapsed ? "sidebar-collapsed" : ""} ${
        isMapView ? "user-map-view" : ""
      } ${isMobileNavOpen ? "mobile-nav-open" : ""}`}
    >
      {isMobileNavOpen ? (
        <button
          aria-label="Đóng menu chức năng"
          className="mobile-nav-scrim"
          onClick={() => setIsMobileNavOpen(false)}
          type="button"
        />
      ) : null}

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
          <UserNavGroup items={primaryNav} view={view} onViewChange={handleUserViewChange} />
          <div className="user-nav-divider" />
          <UserNavGroup items={secondaryNav} view={view} onViewChange={handleUserViewChange} />
        </nav>
        <div className="agent-card user-agent-card">
          <span className="eyebrow">Hỗ trợ</span>
          <strong>Thiết bị EcoSort</strong>
          <div className={agentError ? "system-pill offline" : "system-pill"}>
            <span className="pulse-dot" />
            <span>{agentError ? "Cần tải lại dữ liệu" : "Đang đồng bộ"}</span>
          </div>
        </div>
        <button
          aria-label={isSidebarCollapsed ? "Mở rộng thanh điều hướng" : "Thu gọn thanh điều hướng"}
          className="sidebar-toggle"
          onClick={() => updateSidebarCollapsed(!isSidebarCollapsed)}
          title={isSidebarCollapsed ? "Mở rộng" : "Thu gọn"}
          type="button"
        >
          {isSidebarCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
        </button>
      </aside>

      <nav className="mobile-bottom-taskbar" aria-label="User navigation">
        {mobileTaskbarNav.map((item) => (
          <MobileNavButton item={item} key={item.id} view={view} onViewChange={handleUserViewChange} />
        ))}
        <button
          aria-controls="mobile-user-nav-drawer"
          aria-expanded={isMobileNavOpen}
          aria-label={isMobileNavOpen ? "Đóng tất cả chức năng" : "Mở tất cả chức năng"}
          className={`mobile-taskbar-item ${isMobileNavOpen ? "active" : ""}`}
          onClick={() => setIsMobileNavOpen((current) => !current)}
          ref={mobileMenuButtonRef}
          type="button"
        >
          <Menu aria-hidden="true" focusable="false" size={20} />
          <span>Tất cả</span>
        </button>
      </nav>

      {isMobileNavOpen ? (
        <div
          aria-label="Tất cả chức năng người dùng"
          aria-modal="true"
          className="mobile-nav-drawer"
          id="mobile-user-nav-drawer"
          ref={mobileDrawerRef}
          role="dialog"
        >
          <div className="mobile-nav-drawer-header">
            <div>
              <strong>Chức năng</strong>
              <span>Chọn mục cần mở</span>
            </div>
            <button aria-label="Đóng menu chức năng" className="icon-button" onClick={() => setIsMobileNavOpen(false)} type="button">
              <X aria-hidden="true" focusable="false" size={18} />
            </button>
          </div>
          <nav aria-label="Danh sách chức năng người dùng" className="mobile-nav-drawer-list">
            <UserNavGroup items={mobileDrawerNav} view={view} onViewChange={handleUserViewChange} />
          </nav>
        </div>
      ) : null}

      <main className="workspace user-workspace">
        <header className="topbar user-topbar">
          <strong className="stitch-topbar-title">Trash Sorter Pro</strong>
          <div className="stitch-user-search" aria-label="Trạng thái dữ liệu người dùng">
            <span>Dữ liệu đồng bộ từ EcoSort Cloud</span>
          </div>
          <AccountControl auth={auth} busy={busy} onLogout={props.onLogout} />
        </header>

        {isMapView ? null : <UserHeroSummary analytics={analytics} auth={auth} busy={busy} />}

        {view !== "account" && !isMapView ? (
          <div className="user-range-row">
            <div>
              <span className="eyebrow">Khoảng thời gian</span>
              <strong>Xem theo ngày và tháng</strong>
            </div>
            <RangeSelector rangeDays={rangeDays} onRangeChange={props.onRangeChange} />
          </div>
        ) : null}

        {agentError ? <div className="alert">Dữ liệu chưa sẵn sàng: {agentError}</div> : null}
        {notice && !agentError && !isMapView ? <div className="success">{notice}</div> : null}

        <section className="content-grid user-dashboard-grid">
          <UserRouteContent {...props} />
        </section>

        {props.chatbotEnabled ? (
          <RoleChatbotLauncher
            answer={chatAnswer}
            busy={chatBusy}
            label="EcoPet"
            placeholder="Hỏi EcoPet..."
            question={chatQuestion}
            role="user"
            statusText="EcoPet sẵn sàng đồng hành cùng thói quen phân loại rác của bạn."
            title="EcoPet"
            onCancel={props.onCancelChat}
            onAsk={props.onChatRequest}
            onQuestionChange={props.onChatQuestionChange}
          />
        ) : null}
      </main>
    </div>
  );
}

function MobileNavButton({
  item,
  onViewChange,
  view
}: {
  item: UserNavItem;
  view: UserView;
  onViewChange: (value: UserView) => void;
}) {
  const Icon = item.icon;
  return (
    <a
      aria-current={view === item.id ? "page" : undefined}
      aria-label={item.label}
      className={view === item.id ? "mobile-taskbar-item active" : "mobile-taskbar-item"}
      href={item.href}
      onClick={(event) => {
        event.preventDefault();
        onViewChange(item.id);
      }}
      title={item.label}
    >
      <Icon aria-hidden="true" focusable="false" size={20} />
      <span>{item.label}</span>
    </a>
  );
}

function UserNavGroup({
  items,
  onViewChange,
  view
}: {
  items: UserNavItem[];
  view: UserView;
  onViewChange: (value: UserView) => void;
}) {
  return (
    <>
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <a
            aria-current={view === item.id ? "page" : undefined}
            aria-label={item.label}
            className={view === item.id ? "nav-item active" : "nav-item"}
            href={item.href}
            key={item.id}
            onClick={(event) => {
              event.preventDefault();
              onViewChange(item.id);
            }}
            title={item.label}
          >
            <Icon aria-hidden="true" focusable="false" size={18} />
            <span>{item.label}</span>
          </a>
        );
      })}
    </>
  );
}
