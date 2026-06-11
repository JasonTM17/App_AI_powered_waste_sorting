"use client";

type StatusPillProps = {
  ok: boolean;
  text: string;
};

export function StatusPill({ ok, text }: StatusPillProps) {
  return <span className={ok ? "status-pill ok" : "status-pill warn"}>{text}</span>;
}
