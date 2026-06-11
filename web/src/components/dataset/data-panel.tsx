"use client";

import { ChangeEvent } from "react";
import { RefreshCcw, Upload } from "lucide-react";

import type {
  DatasetBox,
  DatasetItem,
  DatasetSummary,
  DatasetAnnotationResponse
} from "@/lib/agent";
import type { BulkAction, ClassOption, TrustedFilter } from "./data-panel-types";
import { AnnotationEditor } from "@/components/dataset/annotation-editor";
import { DataPanelList } from "@/components/dataset/data-panel-list";

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

// --- MetricCard ---

function MetricCard({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="metric-card">
      <span className="eyebrow">{label}</span>
      <strong>{value}</strong>
      <small>{detail || "-"}</small>
    </div>
  );
}

// --- Props ---

export type DataPanelProps = {
  annotation: DatasetAnnotationResponse | null;
  annotationBoxes: DatasetBox[];
  busy: boolean;
  classFilter: string;
  classOptions: ClassOption[];
  importSource: string;
  itemLimit: number;
  itemOffset: number;
  itemTotal: number;
  items: DatasetItem[];
  imageToken: string;
  manualClass: string;
  search: string;
  selectedPaths: string[];
  sourceFilter: string;
  summary: DatasetSummary | null;
  trustedFilter: TrustedFilter;
  onAnnotate: (itemId: string) => void;
  onAnnotationBoxesChange: (boxes: DatasetBox[]) => void;
  onBulk: (action: BulkAction) => void;
  onClassChange: (value: string) => void;
  onClassFilterChange: (value: string) => void;
  onCloseAnnotation: () => void;
  onDeleteItem: (imagePath: string) => void;
  onImportSourceChange: (value: string) => void;
  onImportZip: (event: ChangeEvent<HTMLInputElement>) => void;
  onPage: (offset: number) => void;
  onRelabelItem: (imagePath: string) => void;
  onApproveAnnotation: () => void;
  onSaveAnnotation: () => void;
  onSourceFilterChange: (value: string) => void;
  onSync: () => void;
  onToggleAll: (checked: boolean) => void;
  onToggleSelected: (path: string) => void;
  onTrustedFilterChange: (value: TrustedFilter) => void;
};

// --- Component ---

export function DataPanel({
  annotation,
  annotationBoxes,
  busy,
  classFilter,
  classOptions,
  importSource,
  itemLimit,
  itemOffset,
  itemTotal,
  items,
  imageToken,
  manualClass,
  search,
  selectedPaths,
  sourceFilter,
  summary,
  trustedFilter,
  onAnnotate,
  onAnnotationBoxesChange,
  onBulk,
  onClassChange,
  onClassFilterChange,
  onCloseAnnotation,
  onDeleteItem,
  onImportSourceChange,
  onImportZip,
  onPage,
  onRelabelItem,
  onApproveAnnotation,
  onSaveAnnotation,
  onSourceFilterChange,
  onSync,
  onToggleAll,
  onToggleSelected,
  onTrustedFilterChange
}: DataPanelProps) {
  const topClasses = Object.entries(summary?.classes ?? {})
    .filter(([name]) => !search || name.toLowerCase().includes(search))
    .sort((a, b) => b[1] - a[1])
    .slice(0, 8);
  const rareClasses = Object.entries(summary?.classes ?? {})
    .filter(([, count]) => count < 100)
    .sort((a, b) => a[1] - b[1])
    .slice(0, 10);
  const baseSources = [
    "roboflow",
    "manual_import",
    "manual_phone_import",
    "manual_camera_capture",
    "manual_web_import",
    "auto_low_conf",
    "unknown",
    "untrusted"
  ];
  const sourceKeys = [
    ...baseSources,
    ...Object.keys(summary?.sources ?? {}).filter((key) => !baseSources.includes(key))
  ];
  const modelClassNames = new Set(classOptions.map((item) => item.name));
  const unknownClasses =
    classOptions.length > 0
      ? Object.entries(summary?.classes ?? {})
          .filter(([name]) => !modelClassNames.has(name))
          .sort((a, b) => b[1] - a[1])
      : [];

  return (
    <section className="content-grid data-grid">
      <div className="stat-row">
        <MetricCard
          label="Ảnh"
          value={formatNumber(summary?.images ?? 0)}
          detail={`${formatNumber(summary?.trainable_total ?? 0)} sẵn sàng train`}
        />
        <MetricCard
          label="Box"
          value={formatNumber(summary?.boxes ?? 0)}
          detail={`DB: ${formatNumber(summary?.box_catalog_total ?? 0)}`}
        />
        <MetricCard
          label="Class"
          value={formatNumber(classOptions.length || summary?.class_catalog_total || 0)}
          detail={`${formatNumber(summary?.class_catalog_total ?? 0)} trong DB, ${formatNumber(unknownClasses.length)} nhãn lạ`}
        />
        <MetricCard
          label="Dataset DB"
          value={formatNumber(summary?.catalog_total ?? 0)}
          detail={
            summary?.needs_sync
              ? "Cần đồng bộ CSDL"
              : `${formatNumber(summary?.needs_review_total ?? 0)} cần duyệt`
          }
        />
      </div>

      {summary?.needs_sync ? (
        <div className="alert full-span">
          CSDL đang lệch với queue ảnh. Bấm “Đồng bộ CSDL” để cập nhật item và box catalog.
        </div>
      ) : null}

      {unknownClasses.length ? (
        <div className="alert full-span">
          Có {formatNumber(unknownClasses.length)} nhãn ngoài model 42 class đang nằm trong catalog:{" "}
          {unknownClasses.map(([name, count]) => `${name} (${formatNumber(count)})`).join(", ")}.
          Giữ chúng ở trạng thái cần duyệt hoặc map lại trước khi export trainset.
        </div>
      ) : null}

      <div className="panel">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Nguồn dataset</span>
            <strong>CSDL training</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" disabled={busy} onClick={onSync} type="button">
              <RefreshCcw size={17} />
              <span>Đồng bộ CSDL</span>
            </button>
          </div>
        </div>
        <div className="source-grid">
          {sourceKeys.map((key) => (
            <button
              className={sourceFilter === key ? "source-tile active" : "source-tile"}
              key={key}
              onClick={() => onSourceFilterChange(sourceFilter === key ? "" : key)}
              type="button"
            >
              <span>{labelSource(key)}</span>
              <strong>{formatNumber(summary?.sources?.[key] ?? 0)}</strong>
            </button>
          ))}
        </div>
        <div className="path-line">Queue: {summary?.queue_dir || "..."}</div>
        <div className="path-line">Catalog: {summary?.catalog_path || "..."}</div>
      </div>

      <div className="panel">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Review dataset</span>
            <strong>Quản trị dữ liệu, không train trong tab này</strong>
          </div>
        </div>
        <p className="muted-copy">
          Thêm ảnh điện thoại, chụp camera, refresh reference và train candidate đã chuyển sang tab Huấn luyện để tránh lẫn với quản trị dataset.
        </p>
        <label className="source-name-field">
          Class thao tác
          <input
            list="data-action-class-options"
            maxLength={64}
            onChange={(event) => onClassChange(event.target.value)}
            placeholder="Chọn class để đổi nhãn hoặc duyệt bbox"
            value={manualClass}
          />
          <datalist id="data-action-class-options">
            {classOptions.map((item) => (
              <option key={`${item.id}-${item.name}-data-action`} value={item.name}>
                {item.name}
              </option>
            ))}
          </datalist>
        </label>
      </div>

      <div className="panel">
        <span className="eyebrow">Roboflow / YOLO ZIP</span>
        <label className="source-name-field">
          Source name
          <input
            maxLength={48}
            onChange={(event) => onImportSourceChange(event.target.value)}
            placeholder="roboflow_waste_candidate"
            value={importSource}
          />
        </label>
        <label className="drop-zone">
          <Upload size={24} />
          <span>{busy ? "Đang xử lý..." : "Chọn file ZIP đã download từ Roboflow"}</span>
          <input accept=".zip" disabled={busy} onChange={onImportZip} type="file" />
        </label>
      </div>

      <div className="panel class-panel">
        <span className="eyebrow">Top classes</span>
        <div className="class-list">
          {topClasses.length ? (
            topClasses.map(([name, count]) => (
              <div className="class-row" key={name}>
                <span>{name}</span>
                <strong>{formatNumber(count)}</strong>
              </div>
            ))
          ) : (
            <div className="empty-state">Chưa có thống kê class.</div>
          )}
        </div>
        <div className="rare-block">
          <span className="eyebrow">Nên bù thêm data</span>
          <div className="class-list">
            {rareClasses.length ? (
              rareClasses.map(([name, count]) => (
                <div className="class-row rare" key={name}>
                  <span>{name}</span>
                  <strong>{formatNumber(count)}</strong>
                </div>
              ))
            ) : (
              <div className="empty-state">Không có class thiếu nghiêm trọng.</div>
            )}
          </div>
        </div>
      </div>

      <DataPanelList
        busy={busy}
        classFilter={classFilter}
        classOptions={classOptions}
        imageToken={imageToken}
        itemLimit={itemLimit}
        itemOffset={itemOffset}
        itemTotal={itemTotal}
        items={items}
        manualClass={manualClass}
        selectedPaths={selectedPaths}
        sourceFilter={sourceFilter}
        sourceKeys={sourceKeys}
        summary={summary}
        trustedFilter={trustedFilter}
        onAnnotate={onAnnotate}
        onBulk={onBulk}
        onClassFilterChange={onClassFilterChange}
        onDeleteItem={onDeleteItem}
        onPage={onPage}
        onRelabelItem={onRelabelItem}
        onSourceFilterChange={onSourceFilterChange}
        onToggleAll={onToggleAll}
        onToggleSelected={onToggleSelected}
        onTrustedFilterChange={onTrustedFilterChange}
      />

      {annotation ? (
        <AnnotationEditor
          annotation={annotation}
          boxes={annotationBoxes}
          busy={busy}
          classOptions={classOptions}
          imageToken={imageToken}
          selectedClass={manualClass}
          onBoxesChange={onAnnotationBoxesChange}
          onClassChange={onClassChange}
          onClose={onCloseAnnotation}
          onApprove={onApproveAnnotation}
          onSave={onSaveAnnotation}
        />
      ) : null}
    </section>
  );
}
