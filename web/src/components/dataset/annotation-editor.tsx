"use client";

import { MouseEvent, useEffect, useState } from "react";
import { CheckCircle2, Save, Trash2, X } from "lucide-react";

import type { DatasetAnnotationResponse, DatasetBox } from "@/lib/agent";
import type { ClassOption } from "./data-panel-types";
import { datasetImageUrl } from "@/lib/agent";

// --- Local helpers ---

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function normalizeBox(xyxy: [number, number, number, number]): [number, number, number, number] {
  return [
    Math.min(xyxy[0], xyxy[2]),
    Math.min(xyxy[1], xyxy[3]),
    Math.max(xyxy[0], xyxy[2]),
    Math.max(xyxy[1], xyxy[3])
  ];
}

function boxStyle(box: DatasetBox, imageSize: { width: number; height: number }) {
  const [x1, y1, x2, y2] = normalizeBox(box.xyxy);
  return {
    left: `${(x1 / imageSize.width) * 100}%`,
    top: `${(y1 / imageSize.height) * 100}%`,
    width: `${((x2 - x1) / imageSize.width) * 100}%`,
    height: `${((y2 - y1) / imageSize.height) * 100}%`
  };
}

// --- Props ---

export type AnnotationEditorProps = {
  annotation: DatasetAnnotationResponse;
  boxes: DatasetBox[];
  busy: boolean;
  classOptions: ClassOption[];
  imageToken: string;
  selectedClass: string;
  onBoxesChange: (boxes: DatasetBox[]) => void;
  onClassChange: (value: string) => void;
  onClose: () => void;
  onApprove: () => void;
  onSave: () => void;
};

// --- Component ---

export function AnnotationEditor({
  annotation,
  boxes,
  busy,
  classOptions,
  imageToken,
  selectedClass,
  onBoxesChange,
  onClassChange,
  onClose,
  onApprove,
  onSave
}: AnnotationEditorProps) {
  const [imageSize, setImageSize] = useState({
    width: Math.max(annotation.item.width ?? 1, 1),
    height: Math.max(annotation.item.height ?? 1, 1)
  });
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [draft, setDraft] = useState<DatasetBox | null>(null);
  const activeOption = classOptions.find((item) => item.name === selectedClass) ?? classOptions[0];

  useEffect(() => {
    setImageSize({
      width: Math.max(annotation.item.width ?? 1, 1),
      height: Math.max(annotation.item.height ?? 1, 1)
    });
    setDragStart(null);
    setDraft(null);
  }, [annotation.item.item_id, annotation.item.width, annotation.item.height]);

  function pointFromEvent(event: MouseEvent<HTMLDivElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    return {
      x: clamp(((event.clientX - rect.left) / rect.width) * imageSize.width, 0, imageSize.width),
      y: clamp(((event.clientY - rect.top) / rect.height) * imageSize.height, 0, imageSize.height)
    };
  }

  function makeBox(start: { x: number; y: number }, end: { x: number; y: number }): DatasetBox {
    const x1 = Math.min(start.x, end.x);
    const y1 = Math.min(start.y, end.y);
    const x2 = Math.max(start.x, end.x);
    const y2 = Math.max(start.y, end.y);
    return {
      cls_id: activeOption?.id ?? 0,
      cls_name: activeOption?.name ?? selectedClass,
      conf: 1,
      xyxy: [x1, y1, x2, y2]
    };
  }

  function startDraw(event: MouseEvent<HTMLDivElement>) {
    const point = pointFromEvent(event);
    setDragStart(point);
    setDraft(makeBox(point, point));
  }

  function moveDraw(event: MouseEvent<HTMLDivElement>) {
    if (!dragStart) {
      return;
    }
    setDraft(makeBox(dragStart, pointFromEvent(event)));
  }

  function endDraw(event: MouseEvent<HTMLDivElement>) {
    if (!dragStart) {
      return;
    }
    const box = makeBox(dragStart, pointFromEvent(event));
    setDragStart(null);
    setDraft(null);
    if (Math.abs(box.xyxy[2] - box.xyxy[0]) < 6 || Math.abs(box.xyxy[3] - box.xyxy[1]) < 6) {
      return;
    }
    onBoxesChange([...boxes, box]);
  }

  function updateBoxClass(index: number, clsName: string) {
    const option = classOptions.find((item) => item.name === clsName);
    onBoxesChange(
      boxes.map((box, boxIndex) =>
        boxIndex === index
          ? { ...box, cls_id: option?.id ?? box.cls_id, cls_name: option?.name ?? clsName }
          : box
      )
    );
  }

  function updateBoxCoord(index: number, coordIndex: number, raw: number) {
    const next = Number.isFinite(raw) ? raw : 0;
    onBoxesChange(
      boxes.map((box, boxIndex) => {
        if (boxIndex !== index) {
          return box;
        }
        const xyxy = [...box.xyxy] as [number, number, number, number];
        xyxy[coordIndex] = clamp(
          next,
          0,
          coordIndex % 2 === 0 ? imageSize.width : imageSize.height
        );
        return { ...box, xyxy: normalizeBox(xyxy) };
      })
    );
  }

  function removeBox(index: number) {
    onBoxesChange(boxes.filter((_, boxIndex) => boxIndex !== index));
  }

  return (
    <div className="annotation-backdrop" role="dialog" aria-modal="true">
      <div className="annotation-modal">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Annotation editor</span>
            <strong>{annotation.item.cls_name || annotation.item.item_id}</strong>
          </div>
          <div className="button-row">
            <button className="secondary-button" onClick={onClose} type="button">
              <X size={16} />
              <span>Đóng</span>
            </button>
            <button className="primary-button" disabled={busy} onClick={onSave} type="button">
              <Save size={17} />
              <span>Lưu bbox</span>
            </button>
            <button className="primary-button" disabled={busy || !boxes.length} onClick={onApprove} type="button">
              <CheckCircle2 size={17} />
              <span>Duyệt bbox</span>
            </button>
          </div>
        </div>

        <div className="annotation-layout">
          <div>
            <div
              className="annotation-canvas"
              onMouseDown={startDraw}
              onMouseMove={moveDraw}
              onMouseUp={endDraw}
            >
              <img
                className="annotation-image"
                src={datasetImageUrl(annotation.item.item_id, imageToken)}
                alt={annotation.item.original_file || annotation.item.item_id}
                onLoad={(event) =>
                  setImageSize({
                    width: event.currentTarget.naturalWidth || 1,
                    height: event.currentTarget.naturalHeight || 1
                  })
                }
              />
              {[...boxes, ...(draft ? [draft] : [])].map((box, index) => {
                const style = boxStyle(box, imageSize);
                const isDraft = index >= boxes.length;
                return (
                  <div
                    className={isDraft ? "annotation-box preview" : "annotation-box"}
                    key={`${box.cls_name}-${index}-${box.xyxy.join("-")}`}
                    style={style}
                  >
                    <span>{box.cls_name}</span>
                  </div>
                );
              })}
            </div>
            <p className="muted">Kéo chuột trên ảnh để tạo bbox. Chọn class mặc định trước khi vẽ.</p>
          </div>

          <aside className="annotation-sidebar">
            <label>
              Class mặc định
              <select value={selectedClass} onChange={(event) => onClassChange(event.target.value)}>
                {classOptions.map((item) => (
                  <option key={`${item.id}-${item.name}-draw`} value={item.name}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="annotation-box-list">
              {boxes.length ? (
                boxes.map((box, index) => (
                  <div className="annotation-box-row" key={`${box.cls_name}-${index}`}>
                    <div className="row-actions">
                      <strong>Box {index + 1}</strong>
                      <button className="danger-button compact-button" onClick={() => removeBox(index)} type="button">
                        <Trash2 size={14} />
                      </button>
                    </div>
                    <select value={box.cls_name} onChange={(event) => updateBoxClass(index, event.target.value)}>
                      {classOptions.map((item) => (
                        <option key={`${item.id}-${item.name}-box-${index}`} value={item.name}>
                          {item.name}
                        </option>
                      ))}
                    </select>
                    <div className="mini-grid">
                      {(["x1", "y1", "x2", "y2"] as const).map((label, coordIndex) => (
                        <label key={label}>
                          {label}
                          <input
                            min={0}
                            onChange={(event) => updateBoxCoord(index, coordIndex, Number(event.target.value))}
                            type="number"
                            value={Math.round(box.xyxy[coordIndex])}
                          />
                        </label>
                      ))}
                    </div>
                  </div>
                ))
              ) : (
                <div className="empty-state">Chưa có bbox. Kéo trên ảnh để vẽ box đầu tiên.</div>
              )}
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}
