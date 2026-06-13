"use client";

import { Camera } from "lucide-react";

import type { HistoryRow } from "@/lib/agent";
import { historyImagePath, openAgentBlob } from "@/lib/agent";

type HistoryPanelProps = {
  imageToken: string;
  rows: HistoryRow[];
};

export function HistoryPanel({ imageToken, rows }: HistoryPanelProps) {
  return (
    <section className="panel">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Thời gian</th>
              <th>Class</th>
              <th>Nhóm</th>
              <th>Thùng</th>
              <th>Độ tin cậy</th>
              <th>UART</th>
              <th>ACK</th>
              <th>Ảnh nhãn</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{row.id}</td>
                <td>{row.ts}</td>
                <td>{row.cls_name}</td>
                <td>{row.route_label || "-"}</td>
                <td>{row.bin_index || "-"}</td>
                <td>{Math.round(row.conf * 100)}%</td>
                <td>{row.uart_command || "-"}</td>
                <td>{row.ack_status || "-"}</td>
                <td>
                  {row.annotated_path ? (
                    <button
                      className="secondary-button compact-button history-image-link"
                      onClick={() => void openAgentBlob(historyImagePath(row.id, "annotated"), imageToken)}
                      type="button"
                    >
                      <Camera size={15} />
                      <span>Mở ảnh</span>
                    </button>
                  ) : (
                    "-"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length ? <div className="empty-state">Chưa có lịch sử nhận diện.</div> : null}
    </section>
  );
}
