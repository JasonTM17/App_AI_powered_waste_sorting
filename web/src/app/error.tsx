"use client";

import { ErrorPanel } from "@/components/primitives/error-panel";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="vi">
      <body
        style={{
          background: "#f7f9fb",
          color: "#191c1e",
          fontFamily:
            '"Be Vietnam Pro", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
          margin: 0,
          minHeight: "100dvh",
        }}
      >
        <div
          style={{
            alignItems: "center",
            display: "flex",
            justifyContent: "center",
            minHeight: 64,
            padding: "0 24px",
            backgroundColor: "#0f172a",
          }}
        >
          <span
            style={{
              color: "#ffffff",
              fontSize: 18,
              fontWeight: 800,
            }}
          >
            Trash Sorter Pro
          </span>
        </div>
        <ErrorPanel
          digest={error.digest ?? "unknown"}
          detail={
            process.env.NODE_ENV !== "production" ? error.message : undefined
          }
          onRetry={reset}
        />
      </body>
    </html>
  );
}
