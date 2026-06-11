"use client";

import { BrainCircuit, ShieldCheck } from "lucide-react";

import type { AppConfig, RuntimeStatus } from "@/lib/agent";
import { NumberField } from "@/components/primitives/number-field";

type SettingsModelPanelProps = {
  config: AppConfig;
  status: RuntimeStatus | null;
  onChange: (patch: (cfg: AppConfig) => AppConfig) => void;
};

export function SettingsModelPanel({ config, status, onChange }: SettingsModelPanelProps) {
  return (
    <>
      <div className="panel">
        <span className="eyebrow">Model</span>
        <div className="form-grid two-col">
          <label>
            Đường dẫn model
            <input
              value={config.model.path}
              onChange={(event) =>
                onChange((cfg) => ({ ...cfg, model: { ...cfg.model, path: event.target.value } }))
              }
            />
          </label>
          <label>
            Thiết bị
            <select
              value={config.model.device}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  model: { ...cfg.model, device: event.target.value as "auto" | "cpu" | "cuda" }
                }))
              }
            >
              <option value="auto">Auto (ưu tiên GPU)</option>
              <option value="cpu">CPU</option>
              <option value="cuda">CUDA</option>
            </select>
          </label>
          <NumberField
            label="Độ tin cậy"
            max={1}
            min={0}
            step={0.01}
            value={config.model.conf_threshold}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, model: { ...cfg.model, conf_threshold: value } }))
            }
          />
          <NumberField
            label="IoU"
            max={1}
            min={0}
            step={0.01}
            value={config.model.iou_threshold}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, model: { ...cfg.model, iou_threshold: value } }))
            }
          />
          <NumberField
            label="Kích thước input"
            min={320}
            step={32}
            value={config.model.input_size}
            onValue={(value) =>
              onChange((cfg) => ({ ...cfg, model: { ...cfg.model, input_size: Math.round(value) } }))
            }
          />
        </div>
      </div>

      <div className="panel">
        <span className="eyebrow">Kaggle 3-Bin Fallback</span>
        <div className="capture-warning">
          <BrainCircuit size={16} />
          <span>Chỉ dùng classifier này khi YOLO thấy Unknown trong ROI; không thay model YOLO production.</span>
        </div>
        <div className="form-grid two-col">
          <label className="check-field">
            <input
              checked={config.three_bin_classifier.enabled}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  three_bin_classifier: {
                    ...cfg.three_bin_classifier,
                    enabled: event.target.checked
                  }
                }))
              }
              type="checkbox"
            />
            Bật fallback 3 thùng
          </label>
          <label className="check-field">
            <input
              checked={config.three_bin_classifier.unknown_only}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  three_bin_classifier: {
                    ...cfg.three_bin_classifier,
                    unknown_only: event.target.checked
                  }
                }))
              }
              type="checkbox"
            />
            Chỉ sửa Unknown object
          </label>
          <label>
            Đường dẫn classifier
            <input
              value={config.three_bin_classifier.model_path}
              onChange={(event) =>
                onChange((cfg) => ({
                  ...cfg,
                  three_bin_classifier: {
                    ...cfg.three_bin_classifier,
                    model_path: event.target.value
                  }
                }))
              }
            />
          </label>
          <NumberField
            label="3-bin confidence"
            max={1}
            min={0}
            step={0.01}
            value={config.three_bin_classifier.min_confidence}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                three_bin_classifier: {
                  ...cfg.three_bin_classifier,
                  min_confidence: value
                }
              }))
            }
          />
          <NumberField
            label="3-bin margin"
            max={1}
            min={0}
            step={0.01}
            value={config.three_bin_classifier.min_margin}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                three_bin_classifier: {
                  ...cfg.three_bin_classifier,
                  min_margin: value
                }
              }))
            }
          />
          <NumberField
            label="Min crop area"
            max={1}
            min={0}
            step={0.001}
            value={config.three_bin_classifier.min_crop_area_ratio}
            onValue={(value) =>
              onChange((cfg) => ({
                ...cfg,
                three_bin_classifier: {
                  ...cfg.three_bin_classifier,
                  min_crop_area_ratio: value
                }
              }))
            }
          />
        </div>
        <div className="policy-strip">
          <ShieldCheck size={18} />
          <div>
            <strong>{status?.three_bin_classifier.running ? "Fallback đang bật" : "Fallback đang tắt"}</strong>
            <span>{status?.three_bin_classifier.message || "models/three_bin_classifier.pt"}</span>
          </div>
        </div>
      </div>
    </>
  );
}
