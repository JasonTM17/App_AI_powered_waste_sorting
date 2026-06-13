"use client";

import { Bell, Bot, Heart, Leaf, MessageSquareText, Send, Share2, Sparkles, Trophy } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import type { AiChatResponse, UserAnalytics, UserExperience } from "@/lib/agent";

type SocialPost = {
  id: string;
  author: string;
  body: string;
  likes: number;
  shares: number;
  comments: number;
  tag: string;
  time: string;
};

const DEFAULT_COMMUNITY_POSTS: SocialPost[] = [
  {
    id: "local-weekly-win",
    author: "Minh Anh",
    body: "Tuần này nhà mình giảm được 12 chai nhựa dùng một lần. Eco Score tăng đều hơn khi gom giấy riêng.",
    likes: 18,
    shares: 5,
    comments: 4,
    tag: "Thử thách tuần",
    time: "Hôm nay"
  },
  {
    id: "school-recycle",
    author: "Nhóm EcoSort",
    body: "Góc phân loại ở trường đang dẫn đầu bảng tuần. Mốc tiếp theo là 80 lượt tái chế sạch.",
    likes: 31,
    shares: 9,
    comments: 7,
    tag: "Cạnh tranh",
    time: "2 giờ trước"
  },
  {
    id: "organic-tip",
    author: "Lan",
    body: "Mình tách rác hữu cơ vào hộp riêng trước khi đổ, cảm biến nhận nhanh hơn và ít nhầm hơn.",
    likes: 14,
    shares: 3,
    comments: 2,
    tag: "Mẹo xanh",
    time: "Hôm qua"
  }
];

const DEFAULT_COMMUNITY_CARDS = [
  {
    id: "weekly-race",
    title: "Đua top tuần",
    message: "Bạn đang ở nhóm cạnh tranh Eco Score local. Hoàn thành thêm thử thách để vượt mốc tiếp theo.",
    metric: "Top 12%",
    share_text: "Mẫu chia sẻ: Tôi vừa tăng Eco Score trên Trash Sorter Pro.",
    tone: "success"
  },
  {
    id: "share-streak",
    title: "Chuỗi chia sẻ",
    message: "Đăng một cập nhật xanh để giữ nhịp cộng đồng và nhận điểm động viên.",
    metric: "3 bài",
    share_text: "Nội dung đăng sẽ lưu local trong phiên này.",
    tone: "info"
  },
  {
    id: "team-goal",
    title: "Mục tiêu cộng đồng",
    message: "Nhóm EcoSort local còn 24 lượt phân loại đúng để mở huy hiệu tuần.",
    metric: "76/100",
    share_text: "Kêu gọi bạn bè cùng phân loại sạch hơn.",
    tone: "warning"
  }
];

const COMMUNITY_STORAGE_KEY = "trash-sorter-user-community-posts";

const ECOPET_PROMPTS = [
  "Hôm nay mình phân loại rác thế nào?",
  "Gợi ý một việc nhỏ để tăng Eco Score",
  "Mình nên chú ý thùng nào trước?",
  "Tóm tắt thói quen 7 ngày gần đây"
];

export function UserEcoPetScreen({
  analytics,
  answer,
  busy,
  question,
  onAsk,
  onQuestionChange
}: {
  analytics: UserAnalytics | null;
  answer: AiChatResponse | null;
  busy: boolean;
  question: string;
  onAsk: (value?: string) => void;
  onQuestionChange: (value: string) => void;
}) {
  const advice = analytics?.advice?.[0] ?? analytics?.insights?.[0] ?? null;
  const score = analytics?.eco_score?.score ?? 0;
  const recycleRate = analytics?.eco_score?.recyclable_rate ?? 0;

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onAsk(question);
  }

  return (
    <section className="ecopet-layout">
      <div className="user-panel ecopet-hero-card">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">EcoPet AI</span>
            <strong>Trợ lý thói quen xanh</strong>
          </div>
          <Bot size={23} />
        </div>
        <p>
          EcoPet đọc dữ liệu phân loại của tài khoản này, trả lời theo dashboard User và giữ nội dung ngắn gọn để bạn dễ hành động.
        </p>
        <div className="ecopet-metric-row">
          <span>
            <strong>{score}</strong>
            <small>Eco Score</small>
          </span>
          <span>
            <strong>{Math.round(recycleRate)}%</strong>
            <small>Tái chế</small>
          </span>
          <span>
            <strong>{analytics?.today_total ?? 0}</strong>
            <small>Hôm nay</small>
          </span>
        </div>
      </div>

      <div className="user-panel ecopet-chat-card">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">Hỏi nhanh</span>
            <strong>Chat với EcoPet</strong>
          </div>
          <Sparkles size={21} />
        </div>
        <div className="ecopet-prompt-grid">
          {ECOPET_PROMPTS.map((prompt) => (
            <button
              className="secondary-button"
              disabled={busy}
              key={prompt}
              onClick={() => {
                onQuestionChange(prompt);
                onAsk(prompt);
              }}
              type="button"
            >
              {prompt}
            </button>
          ))}
        </div>
        <form className="ecopet-chat-form" onSubmit={submit}>
          <input
            aria-label="Câu hỏi cho EcoPet"
            onChange={(event) => onQuestionChange(event.target.value)}
            placeholder="Nhập câu hỏi cho EcoPet..."
            value={question}
          />
          <button className="primary-button" disabled={busy} type="submit">
            <Send size={16} />
            <span>{busy ? "Đang hỏi" : "Gửi"}</span>
          </button>
        </form>
        <article className="ecopet-answer-card" aria-live="polite">
          <strong>{answer ? "EcoPet trả lời" : "Gợi ý hiện tại"}</strong>
          <p>{answer?.message || advice?.message || "Hỏi EcoPet để nhận gợi ý dựa trên lịch sử phân loại của bạn."}</p>
          {answer?.quota_remaining != null ? (
            <small>
              Còn {answer.quota_remaining}/{answer.quota_limit ?? 36} lượt hỏi trong tháng.
            </small>
          ) : null}
        </article>
      </div>

      <div className="user-panel ecopet-tip-card">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">Gợi ý xanh</span>
            <strong>{advice?.title || "Bắt đầu từ việc nhỏ"}</strong>
          </div>
          <Leaf size={21} />
        </div>
        <p>
          {advice?.message ||
            "Tách riêng chai/lon tái chế trước khi bỏ vào thùng để cảm biến đọc ổn định hơn và tăng điểm thói quen xanh."}
        </p>
      </div>
    </section>
  );
}

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
  const rows = experience?.leaderboard ?? [];
  const current = rows.find((row) => row.current_user) ?? rows[0] ?? null;
  const next = current ? rows.find((row) => row.rank < current.rank) ?? null : null;
  const targetScore = Math.max(1, current?.score ?? 0, next?.score ?? 0);
  const progress = current
    ? Math.min(100, Math.round((current.score / targetScore) * 100))
    : 0;
  const gap = current && next ? Math.max(0, next.score - current.score) : 0;

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
        {current ? (
          <article className="leaderboard-focus-card" data-testid="leaderboard-current-summary">
            <div>
              <span className="eyebrow">Hạng hiện tại</span>
              <strong>#{current.rank} - {current.label}</strong>
              <small>{next ? `Còn ${gap} điểm để vượt ${next.label}` : "Bạn đang dẫn đầu mốc so sánh local."}</small>
            </div>
            <b>{current.score}</b>
            <div className="fill-meter" aria-label="Tiến độ thăng hạng">
              <span style={{ width: `${progress}%` }} />
            </div>
          </article>
        ) : (
          <Empty text="Chưa có dữ liệu xếp hạng." />
        )}
        {rows.map((row) => (
          <div
            className={row.current_user ? "leaderboard-row current" : "leaderboard-row"}
            data-testid={row.current_user ? "leaderboard-current-row" : undefined}
            key={row.label}
          >
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
  const [draft, setDraft] = useState("");
  const [selectedTag, setSelectedTag] = useState("Thử thách tuần");
  const [posts, setPosts] = useState(DEFAULT_COMMUNITY_POSTS);
  const [notice, setNotice] = useState("");
  const [hasLoadedLocalPosts, setHasLoadedLocalPosts] = useState(false);
  const cards = experience?.community_cards?.length ? experience.community_cards : DEFAULT_COMMUNITY_CARDS;
  const socialStats = useMemo(
    () => ({
      likes: posts.reduce((total, post) => total + post.likes, 0),
      shares: posts.reduce((total, post) => total + post.shares, 0),
      comments: posts.reduce((total, post) => total + post.comments, 0)
    }),
    [posts]
  );

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(COMMUNITY_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved) as SocialPost[];
        if (Array.isArray(parsed) && parsed.length) {
          setPosts(parsed.slice(0, 24).map(normalizeSocialPost));
        }
      }
    } catch {
      window.localStorage.removeItem(COMMUNITY_STORAGE_KEY);
    } finally {
      setHasLoadedLocalPosts(true);
    }
  }, []);

  useEffect(() => {
    if (!hasLoadedLocalPosts) {
      return;
    }
    window.localStorage.setItem(COMMUNITY_STORAGE_KEY, JSON.stringify(posts.slice(0, 24)));
  }, [hasLoadedLocalPosts, posts]);

  function publishPost(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const body = draft.trim();
    if (!body) {
      setNotice("Nhập nội dung trước khi đăng.");
      return;
    }
    setPosts((current) => [
      {
        id: `local-${Date.now()}`,
        author: "Bạn",
        body,
        likes: 0,
        shares: 0,
        comments: 0,
        tag: selectedTag,
        time: "Vừa xong"
      },
      ...current
    ]);
    setDraft("");
    setNotice("Đã đăng bài Eco-Share local.");
  }

  function likePost(postId: string) {
    setPosts((current) =>
      current.map((post) => (post.id === postId ? { ...post, likes: post.likes + 1 } : post))
    );
  }

  function sharePost(postId: string) {
    const post = posts.find((item) => item.id === postId);
    setPosts((current) =>
      current.map((post) => (post.id === postId ? { ...post, shares: post.shares + 1 } : post))
    );
    if (post) {
      void copyShareText(post);
    }
    setNotice("Đã copy nội dung chia sẻ và tăng lượt share mô phỏng.");
  }

  function commentPost(postId: string) {
    setPosts((current) =>
      current.map((post) => (post.id === postId ? { ...post, comments: post.comments + 1 } : post))
    );
    setNotice("Đã thêm một bình luận cổ vũ mô phỏng.");
  }

  return (
    <section className="community-layout">
      <div className="user-card-grid community-summary-grid">
        {cards.map((card) => (
          <article className={`user-panel community-card ${card.tone}`} key={card.id}>
            <span className="eyebrow">Eco-Share local</span>
            <strong>{card.title}</strong>
            <p>{card.message}</p>
            <b>{card.metric}</b>
            {card.share_text ? <small>{card.share_text}</small> : null}
          </article>
        ))}
      </div>

      <section className="user-panel social-composer-panel">
        <div className="user-panel-heading inline">
          <div>
            <span className="eyebrow">Mạng xã hội local</span>
            <strong>Đăng bài Eco-Share</strong>
          </div>
          <MessageSquareText size={21} />
        </div>
        <form className="social-composer" onSubmit={publishPost}>
          <label>
            Chủ đề
            <select value={selectedTag} onChange={(event) => setSelectedTag(event.target.value)}>
              <option>Thử thách tuần</option>
              <option>Cạnh tranh</option>
              <option>Mẹo xanh</option>
              <option>Eco Score</option>
            </select>
          </label>
          <label>
            Nội dung
            <textarea
              maxLength={220}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Chia sẻ một thành tích phân loại rác hoặc mẹo xanh..."
              value={draft}
            />
          </label>
          <div className="social-composer-actions">
            <span>
              {notice ||
                `${socialStats.likes} lượt thích, ${socialStats.shares} lượt chia sẻ, ${socialStats.comments} bình luận mô phỏng`}
            </span>
            <button className="primary-button" type="submit">
              <Send size={16} />
              <span>Đăng bài</span>
            </button>
          </div>
        </form>
      </section>

      <section className="social-feed" aria-label="Bài viết Eco-Share local">
        {posts.map((post) => (
          <article className="user-panel social-post-card" key={post.id}>
            <header>
              <div>
                <strong>{post.author}</strong>
                <span>{post.time} - {post.tag}</span>
              </div>
              <Trophy size={18} />
            </header>
            <p>{post.body}</p>
            <div className="social-post-actions">
              <button type="button" onClick={() => likePost(post.id)}>
                <Heart size={16} />
                <span>{post.likes}</span>
              </button>
              <button type="button" onClick={() => sharePost(post.id)}>
                <Share2 size={16} />
                <span>{post.shares}</span>
              </button>
              <button type="button" onClick={() => commentPost(post.id)}>
                <MessageSquareText size={16} />
                <span>{post.comments}</span>
              </button>
            </div>
          </article>
        ))}
      </section>
    </section>
  );
}

async function copyShareText(post: SocialPost) {
  const text = `${post.body}\n\n#TrashSorterPro #EcoShare`;
  try {
    if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    }
  } catch {
    // Clipboard support is optional; the local share count still updates.
  }
}

function normalizeSocialPost(post: SocialPost): SocialPost {
  return {
    ...post,
    likes: Number.isFinite(post.likes) ? post.likes : 0,
    shares: Number.isFinite(post.shares) ? post.shares : 0,
    comments: Number.isFinite(post.comments) ? post.comments : 0
  };
}

export function ExperienceChallenges({ experience }: { experience: UserExperience | null }) {
  const challenges = experience?.challenges ?? [];
  return (
    <section className="user-panel challenge-panel">
      <div className="user-panel-heading inline">
        <div>
          <span className="eyebrow">Thử thách</span>
          <strong>Tiến độ thói quen xanh</strong>
        </div>
        <Trophy size={21} />
      </div>
      {challenges.length === 0 ? <Empty text="Chưa có thử thách trong khoảng thời gian này." /> : null}
      {challenges.map((item) => {
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
  const route = safeUserRoute(item.route);
  return (
    <article className={`experience-card ${item.severity ?? "info"}`}>
      <strong>{item.title}</strong>
      <p>{item.message}</p>
      {route ? <a href={route}>{item.action_label || "Xem"}</a> : null}
    </article>
  );
}

function safeUserRoute(route?: string) {
  const clean = String(route || "").trim();
  return clean.startsWith("/user/") ? clean : "";
}

function Empty({ text }: { text: string }) {
  return <div className="empty-state">{text}</div>;
}
