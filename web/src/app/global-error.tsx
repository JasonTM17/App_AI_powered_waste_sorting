"use client";

import { ErrorPanel } from "@/components/primitives/error-panel";

export default function GlobalError({
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
