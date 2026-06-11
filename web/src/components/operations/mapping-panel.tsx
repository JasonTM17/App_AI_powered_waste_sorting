"use client";

import { Save } from "lucide-react";

import type { ClassMapping } from "@/lib/agent";

const BIN_LABELS: Record<string, string> = {
  O: "Hữu cơ",
  R: "Vô cơ",
  I: "Tái chế"
};

function formatNumber(value: number) {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

type MappingPanelProps = {
  busy: boolean;
  mappings: ClassMapping[];
  search: string;
  onChange: (index: number, patch: Partial<ClassMapping>) => void;
  onSave: () => void;
};

export function MappingPanel({
  busy,
  mappings,
  search,
  onChange,
  onSave
}: MappingPanelProps) {
  const visibleMappings = mappings
    .map((mapping, index) => ({ mapping, index }))
    .filter(({ mapping }) => !search || mapping.class_name.toLowerCase().includes(search));
  return (
    <section className="panel">
      <div className="panel-toolbar no-pad">
        <div>
          <span className="eyebrow">3 thùng vận hành</span>
          <strong>{formatNumber(mappings.length)} class → Hữu cơ / Tái chế / Vô cơ</strong>
        </div>
        <button className="primary-button" disabled={busy || !mappings.length} onClick={onSave} type="button">
          <Save size={17} />
          <span>Lưu mapping</span>
        </button>
      </div>
      <div className="table-wrap">
        <table className="editable-table">
          <thead>
            <tr>
              <th>Class</th>
              <th>Lệnh</th>
              <th>Thùng</th>
              <th>Nhóm</th>
              <th>Bật</th>
            </tr>
          </thead>
          <tbody>
            {visibleMappings.map(({ mapping, index }) => {
              const command = mapping.command.toUpperCase();
              const binLabel = BIN_LABELS[command] || "Tùy chỉnh";
              return (
                <tr key={`${mapping.class_name}-${index}`}>
                  <td>
                    <input
                      value={mapping.class_name}
                      onChange={(event) => onChange(index, { class_name: event.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      className="command-input"
                      maxLength={1}
                      value={mapping.command}
                      onChange={(event) =>
                        onChange(index, { command: event.target.value.slice(0, 1).toUpperCase() })
                      }
                    />
                  </td>
                  <td>
                    <input
                      max={9}
                      min={1}
                      type="number"
                      value={mapping.bin_index}
                      onChange={(event) => onChange(index, { bin_index: Number(event.target.value) })}
                    />
                  </td>
                  <td>
                    <span className={`bin-pill bin-pill-${command.toLowerCase()}`}>{binLabel}</span>
                  </td>
                  <td>
                    <input
                      checked={mapping.enabled}
                      onChange={(event) => onChange(index, { enabled: event.target.checked })}
                      type="checkbox"
                    />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {!visibleMappings.length ? <div className="empty-state">Không có mapping khớp bộ lọc hiện tại.</div> : null}
    </section>
  );
}
