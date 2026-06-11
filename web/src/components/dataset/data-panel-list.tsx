"use client";

import { AlertTriangle, CheckCircle2, ChevronLeft, ChevronRight, Pencil, Save, Trash2 } from "lucide-react";

import type { DatasetItem, DatasetSummary } from "@/lib/agent";
import { datasetImageUrl } from "@/lib/agent";
import { StatusPill } from "@/components/primitives/status-pill";

import type { BulkAction, ClassOption, TrustedFilter } from "./data-panel-types";

// --- Local helpers ---

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

function labelSource(source: string) {
  if (source === "roboflow") return "Roboflow";
  if (source === "manual_import") return "Thủ công";
  if (source === "manual_phone_import") return "Ảnh điện thoại";
  if (source === "manual_camera_capture") return "Camera thủ công";
  if (source === "manual_web_import") return "Ảnh URL";
  if (source === "auto_low_conf") return "Auto cần duyệt";
  if (source === "untrusted") return "Data lạ";
  if (source === "unknown") return "Unknown";
  return source;
}

function datasetTrustLabel(item: DatasetItem) {
  const state = item.trust_state || (item.trusted ? "trainable" : "needs_review");
  if (state === "trainable") return "Trainable";
  if (state === "needs_review") return item.bbox_reviewed ? "Cần duyệt" : "Cần duyệt bbox";
  if (state === "quarantine") return "Cách ly";
  if (state === "hard_negative") return "Mẫu âm";
  if (state === "holdout") return "Holdout";
  if (state === "excluded") return "Không train";
  return item.trusted ? "Trainable" : "Cần duyệt";
}

function datasetTrustDetails(item: DatasetItem) {
  const details = [
    item.review_reason,
    item.quarantine_reason,
    ...(item.trust_reasons ?? [])
  ].filter(Boolean);
  return Array.from(new Set(details)).slice(0, 3).join(", ");
}

// --- Props ---

export type DataPanelListProps = {
  busy: boolean;
  classFilter: string;
  classOptions: ClassOption[];
  imageToken: string;
  itemLimit: number;
  itemOffset: number;
  itemTotal: number;
  items: DatasetItem[];
  manualClass: string;
  selectedPaths: string[];
  sourceFilter: string;
  sourceKeys: string[];
  summary: DatasetSummary | null;
  trustedFilter: TrustedFilter;
  onAnnotate: (itemId: string) => void;
  onBulk: (action: BulkAction) => void;
  onClassFilterChange: (value: string) => void;
  onDeleteItem: (imagePath: string) => void;
  onPage: (offset: number) => void;
  onRelabelItem: (imagePath: string) => void;
  onSourceFilterChange: (value: string) => void;
  onToggleAll: (checked: boolean) => void;
  onToggleSelected: (path: string) => void;
  onTrustedFilterChange: (value: TrustedFilter) => void;
};

// --- Component ---

export function DataPanelList({
  busy,
  classFilter,
  classOptions,
  imageToken,
  itemLimit,
  itemOffset,
  itemTotal,
  items,
  manualClass,
  selectedPaths,
  sourceFilter,
  sourceKeys,
  summary,
  trustedFilter,
  onAnnotate,
  onBulk,
  onClassFilterChange,
  onDeleteItem,
  onPage,
  onRelabelItem,
  onSourceFilterChange,
  onToggleAll,
  onToggleSelected,
  onTrustedFilterChange
}: DataPanelListProps) {
  const allVisibleSelected = items.length > 0 && items.every((item) => selectedPaths.includes(item.image_path));
  const pageStart = itemTotal ? itemOffset + 1 : 0;
  const pageEnd = Math.min(itemOffset + itemLimit, itemTotal);

  return (
    <div className="panel full-span">
      <div className="panel-toolbar no-pad">
        <div>
          <span className="eyebrow">Duyệt dataset</span>
          <strong>
            {formatNumber(pageStart)}-{formatNumber(pageEnd)} / {formatNumber(itemTotal)} bản ghi
          </strong>
        </div>
        <span className="muted">Class thao tác: {manualClass || "chưa chọn"}</span>
      </div>

      <div className="filter-grid">
        <label>
          Nguồn
          <select value={sourceFilter} onChange={(event) => onSourceFilterChange(event.target.value)}>
            <option value="">Tất cả nguồn</option>
            {sourceKeys.map((key) => (
              <option key={key} value={key}>
                {labelSource(key)} ({formatNumber(summary?.sources?.[key] ?? 0)})
              </option>
            ))}
          </select>
        </label>
        <label>
          Class
          <select value={classFilter} onChange={(event) => onClassFilterChange(event.target.value)}>
            <option value="">Tất cả class</option>
            {classOptions.map((item) => (
              <option key={`${item.id}-${item.name}-filter`} value={item.name}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Trạng thái
          <select value={trustedFilter} onChange={(event) => onTrustedFilterChange(event.target.value as TrustedFilter)}>
            <option value="all">Tất cả</option>
            <option value="trusted">Đã tin cậy</option>
            <option value="untrusted">Cần duyệt</option>
          </select>
        </label>
        <div className="pagination-row compact">
          <button
            className="secondary-button compact-button"
            disabled={busy || itemOffset <= 0}
            onClick={() => onPage(itemOffset - itemLimit)}
            type="button"
          >
            <ChevronLeft size={15} />
            <span>Trước</span>
          </button>
          <button
            className="secondary-button compact-button"
            disabled={busy || itemOffset + itemLimit >= itemTotal}
            onClick={() => onPage(itemOffset + itemLimit)}
            type="button"
          >
            <span>Sau</span>
            <ChevronRight size={15} />
          </button>
        </div>
      </div>

      <div className="bulk-toolbar">
        <strong>{formatNumber(selectedPaths.length)} ảnh đã chọn</strong>
        <button
          className="secondary-button compact-button"
          disabled={busy || !selectedPaths.length || !manualClass}
          onClick={() => onBulk("relabel")}
          type="button"
        >
          <Save size={15} />
          <span>Đổi nhãn</span>
        </button>
        <button
          className="secondary-button compact-button"
          disabled={busy || !selectedPaths.length}
          onClick={() => onBulk("mark_trusted")}
          type="button"
        >
          <CheckCircle2 size={15} />
          <span>Duyệt train</span>
        </button>
        <button
          className="secondary-button compact-button"
          disabled={busy || !selectedPaths.length}
          onClick={() => onBulk("mark_untrusted")}
          type="button"
        >
          <AlertTriangle size={15} />
          <span>Loại train</span>
        </button>
        <button
          className="danger-button compact-button"
          disabled={busy || !selectedPaths.length}
          onClick={() => onBulk("quarantine")}
          type="button"
        >
          <AlertTriangle size={15} />
          <span>Cách ly meta</span>
        </button>
        <button
          className="danger-button compact-button"
          disabled={busy || !selectedPaths.length}
          onClick={() => onBulk("delete")}
          type="button"
        >
          <Trash2 size={15} />
          <span>Xóa</span>
        </button>
      </div>

      <div className="table-wrap">
        <table className="dataset-table">
          <thead>
            <tr>
              <th className="select-col">
                <input checked={allVisibleSelected} onChange={(event) => onToggleAll(event.target.checked)} type="checkbox" />
              </th>
              <th>Ảnh</th>
              <th>Source</th>
              <th>Class</th>
              <th>Box</th>
              <th>Trust</th>
              <th>Path</th>
              <th>Thao tác</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.item_id}>
                <td className="select-col">
                  <input
                    checked={selectedPaths.includes(item.image_path)}
                    onChange={() => onToggleSelected(item.image_path)}
                    type="checkbox"
                  />
                </td>
                <td>
                  <img className="thumb" src={datasetImageUrl(item.item_id, imageToken)} alt="" loading="lazy" />
                </td>
                <td>
                  <span className="source-badge">{labelSource(item.source)}</span>
                </td>
                <td>{item.cls_name || "-"}</td>
                <td>{formatNumber(item.box_count)}</td>
                <td>
                  <div className="trust-cell" title={datasetTrustDetails(item)}>
                    <StatusPill ok={item.trusted} text={datasetTrustLabel(item)} />
                    {datasetTrustDetails(item) ? <small>{datasetTrustDetails(item)}</small> : null}
                  </div>
                </td>
                <td className="table-path" title={item.image_path}>
                  {item.image_path}
                </td>
                <td>
                  <div className="row-actions">
                    <button
                      aria-label="Mở bbox editor"
                      className="secondary-button compact-button icon-only"
                      disabled={busy}
                      onClick={() => onAnnotate(item.item_id)}
                      title="Mở bbox editor"
                      type="button"
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      aria-label="Đổi nhãn theo class đang chọn"
                      className="secondary-button compact-button icon-only"
                      disabled={busy || !manualClass}
                      onClick={() => onRelabelItem(item.image_path)}
                      title="Đổi nhãn"
                      type="button"
                    >
                      <Save size={15} />
                    </button>
                    <button
                      aria-label="Xóa ảnh khỏi dataset"
                      className="danger-button compact-button icon-only"
                      disabled={busy}
                      onClick={() => onDeleteItem(item.image_path)}
                      title="Xóa ảnh"
                      type="button"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!items.length ? (
        <div className="empty-state">Chưa có item nào trong catalog hoặc bộ lọc hiện tại không khớp.</div>
      ) : null}
    </div>
  );
}
