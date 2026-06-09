import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "EcoSort AI - Trash Sorter Pro",
    short_name: "EcoSort AI",
    description: "Dashboard phân loại rác local cho Admin và User.",
    start_url: "/user/dashboard",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#f7f9fb",
    theme_color: "#1a1c1e",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        purpose: "any"
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "any"
      },
      {
        src: "/icon-512.png",
        sizes: "512x512",
        type: "image/png",
        purpose: "maskable"
      }
    ],
    shortcuts: [
      {
        name: "Dashboard User",
        short_name: "User",
        url: "/user/dashboard",
        icons: [{ src: "/icon-512.png", sizes: "512x512", type: "image/png" }]
      },
      {
        name: "Giám sát Admin",
        short_name: "Admin",
        url: "/admin?tab=live",
        icons: [{ src: "/icon-512.png", sizes: "512x512", type: "image/png" }]
      }
    ]
  };
}
