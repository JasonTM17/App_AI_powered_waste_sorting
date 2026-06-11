"use client";

type LogsPanelProps = {
  lines: string[];
};

export function LogsPanel({ lines }: LogsPanelProps) {
  return (
    <section className="panel">
      <pre className="log-box">{lines.length ? lines.join("\n") : "Chưa có log."}</pre>
    </section>
  );
}
