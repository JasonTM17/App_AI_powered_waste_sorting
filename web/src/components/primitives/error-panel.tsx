"use client";

import { AlertTriangle, Copy, RefreshCcw } from "lucide-react";

interface ErrorPanelProps {
  digest: string;
  detail?: string;
  onRetry?: () => void;
}

export function ErrorPanel({ digest, detail, onRetry }: ErrorPanelProps) {
  const showDetail = process.env.NODE_ENV !== "production" && detail;

  const handleCopy = () => {
    const info = showDetail
      ? `Digest: ${digest}\nDetail: ${detail}`
      : `Digest: ${digest}`;
    navigator.clipboard.writeText(info).catch(() => {});
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "clamp(280px, 50vh, 480px)",
        padding: "32px 16px",
        textAlign: "center",
      }}
    >
      <div
        style={{
          alignItems: "center",
          background: "#ffdad6",
          border: "1px solid rgba(186, 26, 26, 0.35)",
          borderRadius: "999px",
          color: "#93000a",
          display: "inline-flex",
          height: 56,
          justifyContent: "center",
          marginBottom: 20,
          width: 56,
        }}
      >
        <AlertTriangle size={28} />
      </div>

      <h2
        style={{
          color: "#1a1c1e",
          fontSize: "clamp(20px, 3vw, 28px)",
          fontWeight: 600,
          lineHeight: 1.2,
          margin: "0 0 8px",
        }}
      >
        Có lỗi xảy ra
      </h2>

      <p
        style={{
          color: "#5f6b65",
          fontSize: 14,
          lineHeight: 1.55,
          margin: "0 0 16px",
          maxWidth: 480,
        }}
      >
        Đã xảy ra sự cố không mong muốn khi tải trang này. Vui lòng thử lại hoặc
        sao chép thông tin lỗi để báo cáo.
      </p>

      <div
        style={{
          background: "#f2f4f6",
          border: "1px solid #e2e8f0",
          borderRadius: 8,
          color: "#5f6b65",
          fontFamily:
            '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
          fontSize: 12,
          lineHeight: 1.5,
          marginBottom: 16,
          maxWidth: 520,
          overflowWrap: "anywhere",
          padding: "10px 12px",
          textAlign: "left",
          width: "100%",
        }}
      >
        <strong
          style={{ color: "#1a1c1e", display: "block", marginBottom: 4 }}
        >
          Mã lỗi
        </strong>
        {digest}
        {showDetail ? (
          <>
            <br />
            <span style={{ color: "#93000a" }}>{detail}</span>
          </>
        ) : null}
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, justifyContent: "center" }}>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            style={{
              alignItems: "center",
              background: "#064e3b",
              border: "1px solid #064e3b",
              borderRadius: 8,
              color: "#ffffff",
              cursor: "pointer",
              display: "inline-flex",
              font: "inherit",
              fontSize: 14,
              fontWeight: 700,
              gap: 8,
              height: 40,
              justifyContent: "center",
              padding: "0 14px",
            }}
          >
            <RefreshCcw size={16} />
            Thử lại
          </button>
        ) : null}
        <button
          type="button"
          onClick={handleCopy}
          style={{
            alignItems: "center",
            background: "#ffffff",
            border: "1px solid #e2e8f0",
            borderRadius: 8,
            color: "#191c1e",
            cursor: "pointer",
            display: "inline-flex",
            font: "inherit",
            fontSize: 14,
            fontWeight: 700,
            gap: 8,
            height: 40,
            justifyContent: "center",
            padding: "0 14px",
          }}
        >
          <Copy size={16} />
          Sao chép thông tin lỗi
        </button>
      </div>
    </div>
  );
}
