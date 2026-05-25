"use client";

import { ErrorPanel } from "@/components/primitives/error-panel";

export default function ReportIssueError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorPanel
      digest={error.digest ?? "unknown"}
      detail={
        process.env.NODE_ENV !== "production" ? error.message : undefined
      }
      onRetry={reset}
    />
  );
}
