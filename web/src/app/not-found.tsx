import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
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
          <h1
            style={{
              fontSize: "clamp(48px, 8vw, 96px)",
              fontWeight: 800,
              color: "#064e3b",
              margin: "0 0 8px",
              lineHeight: 1,
            }}
          >
            404
          </h1>
          <p
            style={{
              color: "#5f6b65",
              fontSize: 16,
              lineHeight: 1.55,
              margin: "0 0 24px",
              maxWidth: 420,
            }}
          >
            Trang bạn đang tìm không tồn tại hoặc đã được di chuyển.
          </p>
          <Link
            href="/"
            style={{
              alignItems: "center",
              background: "#064e3b",
              border: "1px solid #064e3b",
              borderRadius: 8,
              color: "#ffffff",
              display: "inline-flex",
              fontSize: 14,
              fontWeight: 700,
              gap: 8,
              height: 40,
              justifyContent: "center",
              padding: "0 14px",
              textDecoration: "none",
            }}
          >
            <Home size={16} />
            Về trang chủ
          </Link>
        </div>
      </body>
    </html>
  );
}
