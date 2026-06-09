"use client";

import { Bell, Trophy } from "lucide-react";

import type { UserExperience } from "@/lib/agent";

export function UserNotificationScreen({ experience }: { experience: UserExperience | null }) {
  const rows = experience?.notifications ?? [];
  return (
    <section className="user-panel notification-center">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Trung tâm thông báo</span>
          <strong>Nhắc việc local</strong>
        </div>
        <Bell size={21} />
      </div>
      {rows.length ? rows.map((item) => <ExperienceCard item={item} key={item.id} />) : <Empty text="Chưa có thông báo." />}
    </section>
  );
}

export function UserLeaderboardScreen({ experience }: { experience: UserExperience | null }) {
  return (
    <>
      <ExperienceChallenges experience={experience} />
      <section className="user-panel leaderboard-panel">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">Bảng xếp hạng local</span>
            <strong>Mốc so sánh trên thiết bị</strong>
          </div>
          <Trophy size={21} />
        </div>
        {(experience?.leaderboard ?? []).map((row) => (
          <div className={row.current_user ? "leaderboard-row current" : "leaderboard-row"} key={row.label}>
            <span>#{row.rank}</span>
            <strong>{row.label}</strong>
            <small>{row.detail}</small>
            <b>{row.score}</b>
          </div>
        ))}
      </section>
    </>
  );
}

export function UserCommunityScreen({ experience }: { experience: UserExperience | null }) {
  return (
    <section className="user-card-grid">
      {(experience?.community_cards ?? []).map((card) => (
        <article className={`user-panel community-card ${card.tone}`} key={card.id}>
          <span className="eyebrow">Eco-Share local</span>
          <strong>{card.title}</strong>
          <p>{card.message}</p>
          <b>{card.metric}</b>
          {card.share_text ? <small>{card.share_text}</small> : null}
        </article>
      ))}
    </section>
  );
}

export function ExperienceChallenges({ experience }: { experience: UserExperience | null }) {
  return (
    <section className="user-panel challenge-panel">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Thử thách</span>
          <strong>Tiến độ thói quen xanh</strong>
        </div>
        <Trophy size={21} />
      </div>
      {(experience?.challenges ?? []).map((item) => {
        const pct = Math.min(100, Math.round((item.progress / Math.max(1, item.target)) * 100));
        return (
          <article className="challenge-row" key={item.id}>
            <div>
              <strong>{item.title}</strong>
              <span>{item.description}</span>
            </div>
            <small>
              {Math.round(item.progress)}/{Math.round(item.target)} {item.unit}
            </small>
            <div className="fill-meter">
              <span style={{ width: `${pct}%` }} />
            </div>
          </article>
        );
      })}
    </section>
  );
}

function ExperienceCard({ item }: { item: { title: string; message: string; severity?: string; route?: string; action_label?: string } }) {
  return (
    <article className={`experience-card ${item.severity ?? "info"}`}>
      <strong>{item.title}</strong>
      <p>{item.message}</p>
      {item.route ? <a href={item.route}>{item.action_label || "Xem"}</a> : null}
    </article>
  );
}

function Empty({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}
