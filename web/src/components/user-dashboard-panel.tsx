"use client";

import { RefreshCcw, Recycle, Save, ShieldCheck, Trash2 } from "lucide-react";
import { AGENT_URL, UserDashboard } from "@/lib/agent";

type UserDashboardPanelProps = {
  agentError: string;
  busy: boolean;
  dashboard: UserDashboard | null;
  tokenDraft: string;
  onRefresh: () => void;
  onTokenDraftChange: (value: string) => void;
  onTokenSave: () => void;
};

export function UserDashboardPanel({
  agentError,
  busy,
  dashboard,
  tokenDraft,
  onRefresh,
  onTokenDraftChange,
  onTokenSave
}: UserDashboardPanelProps) {
  return (
    <div className="app-shell user-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Recycle size={24} />
          </div>
          <div>
            <strong>EcoSort AI</strong>
            <span>User dashboard</span>
          </div>
        </div>
        <div className="agent-card">
          <span className="eyebrow">Local Agent</span>
          <strong>{AGENT_URL}</strong>
          <div className={agentError ? "system-pill offline" : "system-pill"}>
            <span className="pulse-dot" />
            <span>{agentError ? "Can token" : "User online"}</span>
          </div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <label className="token-box" aria-label="Role token">
            <ShieldCheck size={17} />
            <input
              onChange={(event) => onTokenDraftChange(event.target.value)}
              placeholder="Nhap user/admin token"
              type="password"
              value={tokenDraft}
            />
            <button className="round-icon" onClick={onTokenSave} title="Luu token" type="button">
              <Save size={17} />
            </button>
          </label>
          <button className="icon-button" disabled={busy} onClick={onRefresh} type="button">
            <RefreshCcw size={18} />
            <span>Refresh</span>
          </button>
        </header>

        <div className="page-heading">
          <div>
            <span className="eyebrow">User view</span>
            <h1>Tinh trang thung rac</h1>
            <p>Chi hien muc do day, thanh phan rac va goi y chung ve thoi quen.</p>
          </div>
        </div>

        {agentError ? <div className="alert">Agent chua san sang: {agentError}</div> : null}

        <section className="content-grid user-dashboard-grid">
          <div className="stat-row">
            {(dashboard?.bins ?? fallbackBins()).map((bin) => (
              <div className="metric-card bin-fill-card" key={bin.bin_index}>
                <div className="metric-icon">
                  <Trash2 size={18} />
                </div>
                <span>Thung {bin.bin_index}</span>
                <strong>{bin.percent}%</strong>
                <div className="fill-meter" aria-label={`Thung ${bin.bin_index} day ${bin.percent}%`}>
                  <span style={{ width: `${bin.percent}%` }} />
                </div>
                <small>
                  {bin.label}
                  {bin.stale ? " - du lieu cu" : ""}
                </small>
              </div>
            ))}
          </div>

          <div className="panel">
            <span className="eyebrow">Rac gan day</span>
            <div className="class-list">
              {dashboard?.recent_waste.length ? (
                dashboard.recent_waste.map((item) => (
                  <div className="class-row" key={item.cls_name}>
                    <span>
                      {item.cls_name}
                      {item.route_label ? ` - ${item.route_label}` : ""}
                    </span>
                    <strong>{item.count}</strong>
                  </div>
                ))
              ) : (
                <div className="empty-state">Chua co du lieu gan day.</div>
              )}
            </div>
          </div>

          <div className="panel">
            <span className="eyebrow">Goi y</span>
            <div className="insight-list">
              {(dashboard?.insights ?? []).map((insight) => (
                <div className={`insight-card ${insight.severity}`} key={insight.kind}>
                  <strong>{insight.title}</strong>
                  <span>{insight.message}</span>
                </div>
              ))}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}

function fallbackBins() {
  return [1, 2, 3].map((binIndex) => ({
    bin_index: binIndex,
    label: `Thung ${binIndex}`,
    percent: 0,
    updated_at: null,
    stale: true
  }));
}
