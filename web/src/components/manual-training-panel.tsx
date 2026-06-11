"use client";

import { BrainCircuit, Camera, Play, RefreshCcw, Square, Upload } from "lucide-react";

import type { CaptureSession, CommonWasteItem, LearnNowStatus, TrainingStatus } from "@/lib/agent";

type ClassOption = {
  id: number;
  name: string;
};

type ManualTrainingPanelProps = {
  busy: boolean;
  captureSession: CaptureSession | null;
  classOptions: ClassOption[];
  commonWasteItems: CommonWasteItem[];
  learnNow: LearnNowStatus | null;
  manualClass: string;
  manualPhoneFileCount: number;
  training: TrainingStatus | null;
  onClassChange: (value: string) => void;
  onCaptureCameraSample: () => void;
  onImportPhoneData: () => void;
  onCaptureSessionFrame: () => void;
  onLearnNowRefresh: () => void;
  onLearnNowTrain: (profile: "micro" | "strong") => void;
  onManualPhoneFiles: (files: FileList | null) => void;
  onStartCaptureSession: () => void;
  onStopCaptureSession: () => void;
};

const FALLBACK_CANONICAL_LABELS: Record<string, string> = {
  "khẩu trang": "Textile",
  "miếng vải": "Textile",
  textile: "Textile",
  "vải": "Textile",
  "vải cũ": "Textile"
};

export function ManualTrainingPanel({
  busy,
  captureSession,
  classOptions,
  commonWasteItems,
  learnNow,
  manualClass,
  manualPhoneFileCount,
  training,
  onClassChange,
  onCaptureCameraSample,
  onImportPhoneData,
  onCaptureSessionFrame,
  onLearnNowRefresh,
  onLearnNowTrain,
  onManualPhoneFiles,
  onStartCaptureSession,
  onStopCaptureSession
}: ManualTrainingPanelProps) {
  const labelKey = manualClass.trim().toLowerCase();
  const aliasHit = commonWasteItems.find((item) => {
    const labels = [item.label, item.canonical_class, ...(item.aliases ?? [])].map((value) =>
      value.trim().toLowerCase()
    );
    return labels.includes(labelKey);
  });
  const canonicalClass =
    aliasHit?.canonical_class ||
    classOptions.find((item) => item.name.trim().toLowerCase() === labelKey)?.name ||
    FALLBACK_CANONICAL_LABELS[labelKey] ||
    "";
  const canonicalKey = (canonicalClass || manualClass).trim().toLowerCase();
  const learnNowSelected =
    (learnNow?.selected?.class_name.toLowerCase() === canonicalKey ? learnNow.selected : null) ??
    learnNow?.classes.find((item) => item.class_name.toLowerCase() === canonicalKey) ??
    null;
  const canImport = Boolean(canonicalClass) && manualPhoneFileCount > 0;
  const canMicroTrain = Boolean(learnNowSelected?.ready_for_micro_train) && !training?.running;
  const canStrongTrain = Boolean(learnNowSelected?.ready_for_strong_train) && !training?.running;

  return (
    <section className="content-grid data-grid">
      <div className="panel full-span">
        <div className="panel-toolbar no-pad">
          <div>
            <span className="eyebrow">Huấn luyện</span>
            <strong>Nhập nhãn trước, rồi mới upload phone/manual</strong>
          </div>
          <div className="path-line">
            {canonicalClass ? `${manualClass.trim()} → ${canonicalClass}` : "Chưa map được nhãn 45 class"}
          </div>
        </div>

        <div className="form-grid two-col">
          <label>
            Nhãn
            <input
              list="manual-training-label-options"
              maxLength={64}
              onChange={(event) => onClassChange(event.target.value)}
              placeholder="vải, pen, plastic bottle..."
              value={manualClass}
            />
            <datalist id="manual-training-label-options">
              {commonWasteItems.map((item) => (
                <option key={`${item.label}-${item.canonical_class}`} value={item.label}>
                  {item.canonical_class}
                </option>
              ))}
              {commonWasteItems.flatMap((item) =>
                (item.aliases ?? []).map((alias) => (
                  <option key={`${item.canonical_class}-${alias}`} value={alias}>
                    {item.canonical_class}
                  </option>
                ))
              )}
              {classOptions.map((item) => (
                <option key={`${item.id}-${item.name}`} value={item.name}>
                  {item.name}
                </option>
              ))}
            </datalist>
          </label>
          <label className="file-field">
            Ảnh điện thoại / thủ công
            <span className="file-picker">
              <Upload size={16} />
              <span>{manualPhoneFileCount ? `${manualPhoneFileCount} ảnh đã chọn` : "Chọn ảnh"}</span>
              <input
                accept="image/*"
                disabled={!canonicalClass}
                multiple
                onChange={(event) => onManualPhoneFiles(event.target.files)}
                type="file"
              />
            </span>
          </label>
        </div>

        <div className="button-row">
          <button className="primary-button" disabled={busy || !canImport} onClick={onImportPhoneData} type="button">
            <Upload size={17} />
            <span>Thêm ảnh phone</span>
          </button>
          <button className="secondary-button" disabled={busy || !canonicalClass} onClick={onCaptureCameraSample} type="button">
            <Camera size={17} />
            <span>Chụp camera</span>
          </button>
          <button className="secondary-button" disabled={busy || !canonicalClass} onClick={onLearnNowRefresh} type="button">
            <RefreshCcw size={17} />
            <span>Làm mới reference</span>
          </button>
          <button className="primary-button" disabled={busy || !canMicroTrain} onClick={() => onLearnNowTrain("micro")} type="button">
            <BrainCircuit size={17} />
            <span>Train nhanh candidate</span>
          </button>
          <button className="secondary-button" disabled={busy || !canStrongTrain} onClick={() => onLearnNowTrain("strong")} type="button">
            <BrainCircuit size={17} />
            <span>Train mạnh candidate</span>
          </button>
        </div>

        <div className="button-row">
          <button
            className="secondary-button"
            disabled={busy || !canonicalClass || Boolean(captureSession?.active)}
            onClick={onStartCaptureSession}
            type="button"
          >
            <Play size={17} />
            <span>Bắt đầu 24 ảnh</span>
          </button>
          <button
            className="primary-button"
            disabled={busy || !captureSession?.active}
            onClick={onCaptureSessionFrame}
            type="button"
          >
            <Camera size={17} />
            <span>Chụp tư thế tiếp theo</span>
          </button>
          <button
            className="secondary-button"
            disabled={busy || !captureSession?.active}
            onClick={onStopCaptureSession}
            type="button"
          >
            <Square size={17} />
            <span>Dừng phiên</span>
          </button>
        </div>

        <div className="class-list">
          {captureSession?.session_id ? (
            <>
              <div className="class-row">
                <span>Phiên chụp</span>
                <strong>
                  {captureSession.accepted_count}/{captureSession.target_count}
                </strong>
              </div>
              <div className="class-row">
                <span>Train / holdout</span>
                <strong>
                  {captureSession.training_count} / {captureSession.holdout_accepted}
                </strong>
              </div>
              <div className="path-line">{captureSession.last_message}</div>
            </>
          ) : null}
          <div className="class-row">
            <span>Reviewed / reference</span>
            <strong>
              {learnNowSelected ? `${learnNowSelected.reviewed_count} / ${learnNowSelected.reference_count}` : "0 / 0"}
            </strong>
          </div>
          <div className="class-row">
            <span>Holdout</span>
            <strong>{learnNowSelected?.holdout_count ?? 0}</strong>
          </div>
          <div className="class-row">
            <span>Thiếu micro / strong</span>
            <strong>
              {learnNowSelected
                ? `${learnNowSelected.missing_for_micro_train} / ${learnNowSelected.missing_for_strong_train}+${learnNowSelected.missing_holdout_for_strong}`
                : "0 / 0"}
            </strong>
          </div>
          <div className="class-row">
            <span>Candidate</span>
            <strong>{training?.best_model_path || "-"}</strong>
          </div>
          <div className="path-line">
            {learnNowSelected?.message || "Chọn nhãn hợp lệ trước, rồi upload ảnh điện thoại để mở annotation review."}
          </div>
        </div>
      </div>
    </section>
  );
}
