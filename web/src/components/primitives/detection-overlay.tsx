"use client";

import type { Detection } from "@/lib/agent";

type DetectionOverlayProps = {
  detections: Detection[];
};

export function DetectionOverlay({ detections }: DetectionOverlayProps) {
  if (!detections.length) {
    return null;
  }
  return (
    <div className="ai-tags">
      {detections.slice(0, 3).map((item, index) => (
        <div className="ai-tag" key={`${item.timestamp}-overlay-${index}`}>
          <span>{item.cls_name}{item.bin_index ? ` -> thùng ${item.bin_index}` : ""}</span>
          <small>{item.source || "YOLO"}</small>
          <strong>{Math.round(item.confidence * 100)}%</strong>
        </div>
      ))}
    </div>
  );
}
