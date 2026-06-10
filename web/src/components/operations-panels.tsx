"use client";

import {
  AlertTriangle,
  Bell,
  CalendarCheck,
  CheckCircle2,
  Cpu,
  Edit3,
  Flag,
  MapPin,
  Plus,
  Save,
  Server,
  ShieldCheck,
  Trash2,
  UserRoundCog,
  UsersRound
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { OperationsBinMap } from "@/components/operations-bin-map";
import type {
  AlertsResponse,
  BinMapResponse,
  BinStation,
  BinStationCreatePayload,
  BinStationPatchPayload,
  CollectionSchedule,
  CollectionSchedulesResponse,
  DeviceIssueCreatePayload,
  OperationDevicesResponse,
  RoleCatalogResponse
} from "@/lib/agent";

type AdminRolesPanelProps = {
  catalog: RoleCatalogResponse | null;
};

type AdminDevicesPanelProps = {
  busy: boolean;
  devices: OperationDevicesResponse | null;
  onSaveDevice: (payload: {
    device_id: string;
    device_name?: string;
    location?: string;
    owner_username?: string;
    status?: string;
    message?: string;
    active?: boolean;
  }) => void;
};

type AdminBinMapPanelProps = {
  busy: boolean;
  map: BinMapResponse | null;
  schedules: CollectionSchedulesResponse | null;
  onCreateStation: (payload: BinStationCreatePayload) => void;
  onDeleteStation: (stationId: string) => void;
  onPatchStation: (stationId: string, payload: BinStationPatchPayload) => void;
  onRefresh: () => void;
};

type AdminAlertsPanelProps = {
  alerts: AlertsResponse | null;
  busy: boolean;
  schedules: CollectionSchedulesResponse | null;
  onPatchAlert: (alertId: string, status: "open" | "acknowledged" | "resolved") => void;
};

type UserMapScreenProps = {
  busy: boolean;
  map: BinMapResponse | null;
  onRefresh: () => void;
};

type UserAlertsScreenProps = {
  alerts: AlertsResponse | null;
};

type UserScheduleScreenProps = {
  busy: boolean;
  collectOnly?: boolean;
  schedules: CollectionSchedulesResponse | null;
  onCompleteCollection: (scheduleId: string, note: string) => void;
};

type UserDeviceIssueScreenProps = {
  busy: boolean;
  map: BinMapResponse | null;
  onReportIssue: (payload: DeviceIssueCreatePayload) => void;
};

const issueTypes = [
  { id: "full_bin", label: "Thùng đầy" },
  { id: "sensor_problem", label: "Lỗi cảm biến" },
  { id: "camera_problem", label: "Lỗi camera" },
  { id: "audio_problem", label: "Lỗi audio" },
  { id: "map_coordinate", label: "Sai tọa độ" },
  { id: "other", label: "Khác" }
];

export function AdminRolesPanel({ catalog }: AdminRolesPanelProps) {
  const roles = catalog?.roles ?? [];
  return (
    <section className="content-grid operations-grid">
      <div className="panel operations-wide-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">RBAC local</span>
            <h2>Quản lý role và quyền</h2>
          </div>
          <ShieldCheck size={22} />
        </div>
        <div className="operations-role-grid">
          {roles.map((role) => (
            <article className="operations-list-card" key={role.role}>
              <div className="operations-row-title">
                {role.role === "admin" ? <UserRoundCog size={18} /> : <UsersRound size={18} />}
                <div>
                  <strong>{role.label}</strong>
                  <small>{role.capabilities.length} quyền đang bật</small>
                </div>
              </div>
              <div className="operations-chip-list">
                {role.capabilities.map((capability) => (
                  <span className="status-chip" key={capability.id} title={capability.description}>
                    {capability.label}
                  </span>
                ))}
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export function AdminDevicesPanel({ busy, devices, onSaveDevice }: AdminDevicesPanelProps) {
  const [form, setForm] = useState({
    active: true,
    device_id: "",
    device_name: "",
    location: "",
    message: "",
    owner_username: "",
    status: "offline"
  });

  return (
    <section className="content-grid operations-grid">
      <div className="panel operations-wide-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Thiết bị</span>
            <h2>Quản lý thiết bị local</h2>
          </div>
          <Server size={22} />
        </div>
        <div className="operations-list">
          {(devices?.devices ?? []).map((device) => (
            <article className="operations-list-card" key={device.device_id}>
              <div className="operations-row-title">
                <Cpu size={18} />
                <div>
                  <strong>{device.device_name || device.device_id}</strong>
                  <small>{device.device_id} - {device.location || "chưa có vị trí"}</small>
                </div>
              </div>
              <span className={device.status === "warning" ? "status-chip warning" : device.active ? "status-chip" : "status-chip muted"}>
                {device.active ? device.status : "inactive"}
              </span>
              <p>{device.message || "Thiết bị chưa gửi trạng thái realtime."}</p>
            </article>
          ))}
        </div>
      </div>
      <aside className="side-panel operations-side-panel">
        <div>
          <span className="eyebrow">Thêm / cập nhật</span>
          <h2>Thiết bị</h2>
        </div>
        <div className="form-grid one-col">
          <label>
            Device ID
            <input onChange={(event) => setForm({ ...form, device_id: event.target.value })} value={form.device_id} />
          </label>
          <label>
            Tên thiết bị
            <input onChange={(event) => setForm({ ...form, device_name: event.target.value })} value={form.device_name} />
          </label>
          <label>
            Khu vực
            <input onChange={(event) => setForm({ ...form, location: event.target.value })} value={form.location} />
          </label>
          <label>
            User phụ trách
            <input onChange={(event) => setForm({ ...form, owner_username: event.target.value })} value={form.owner_username} />
          </label>
          <label>
            Trạng thái
            <select onChange={(event) => setForm({ ...form, status: event.target.value })} value={form.status}>
              <option value="offline">offline</option>
              <option value="online">online</option>
              <option value="warning">warning</option>
            </select>
          </label>
          <label>
            Ghi chú
            <input onChange={(event) => setForm({ ...form, message: event.target.value })} value={form.message} />
          </label>
          <label className="inline-check">
            <input
              checked={form.active}
              onChange={(event) => setForm({ ...form, active: event.target.checked })}
              type="checkbox"
            />
            Đang hoạt động
          </label>
          <button
            className="primary-button"
            disabled={busy || !form.device_id.trim()}
            onClick={() => onSaveDevice(form)}
            type="button"
          >
            <Save size={17} />
            <span>Lưu thiết bị</span>
          </button>
        </div>
      </aside>
    </section>
  );
}

export function AdminBinMapPanel({
  busy,
  map,
  schedules,
  onCreateStation,
  onDeleteStation,
  onPatchStation,
  onRefresh
}: AdminBinMapPanelProps) {
  const [selectedId, setSelectedId] = useState("");
  const selected = map?.stations.find((station) => station.station_id === selectedId) ?? map?.stations[0] ?? null;
  const [form, setForm] = useState<StationFormState>(() => stationToForm(selected));

  useEffect(() => {
    setForm(stationToForm(selected));
  }, [selected]);

  const dueSchedules = (schedules?.schedules ?? []).slice(0, 6);

  return (
    <section className="content-grid operations-grid">
      <OperationsBinMap
        busy={busy}
        map={map}
        selectedStationId={selected?.station_id}
        onRefresh={onRefresh}
        onSelectStation={(station) => setSelectedId(station.station_id)}
      />
      <aside className="side-panel operations-side-panel">
        <div>
          <span className="eyebrow">Tọa độ ứng viên</span>
          <h2>Chỉnh trạm thùng rác</h2>
        </div>
        {selected ? (
          <StationForm
            busy={busy}
            form={form}
            mode="patch"
            onChange={setForm}
            onSubmit={() => onPatchStation(selected.station_id, formToPayload(form))}
          />
        ) : (
          <div className="empty-state">Chọn một trạm trên bản đồ để chỉnh.</div>
        )}
        {selected ? (
          <button className="danger-button" disabled={busy} onClick={() => onDeleteStation(selected.station_id)} type="button">
            <Trash2 size={17} />
            <span>Ngưng hoạt động trạm</span>
          </button>
        ) : null}
      </aside>

      <div className="panel operations-wide-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Thêm mới</span>
            <h2>Tạo trạm thùng rác</h2>
          </div>
          <Plus size={21} />
        </div>
        <CreateStationForm busy={busy} onCreate={onCreateStation} />
      </div>

      <div className="panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Lịch thu gom</span>
            <h2>Sắp tới</h2>
          </div>
          <CalendarCheck size={21} />
        </div>
        <ScheduleList compact schedules={dueSchedules} />
      </div>
    </section>
  );
}

export function AdminAlertsPanel({ alerts, busy, schedules, onPatchAlert }: AdminAlertsPanelProps) {
  return (
    <section className="content-grid operations-grid">
      <div className="panel operations-wide-panel">
        <div className="panel-toolbar">
          <div>
            <span className="eyebrow">Cảnh báo</span>
            <h2>Theo dõi toàn hệ thống</h2>
          </div>
          <Bell size={22} />
        </div>
        <AlertList alerts={alerts?.alerts ?? []} busy={busy} onPatchAlert={onPatchAlert} />
      </div>
      <aside className="side-panel operations-side-panel">
        <div>
          <span className="eyebrow">Lịch</span>
          <h2>Thu gom cần chú ý</h2>
        </div>
        <ScheduleList compact schedules={schedules?.schedules ?? []} />
      </aside>
    </section>
  );
}

export function UserMapScreen({ busy, map, onRefresh }: UserMapScreenProps) {
  const [selectedId, setSelectedId] = useState("");
  const selected = map?.stations.find((station) => station.station_id === selectedId) ?? map?.stations[0] ?? null;
  return (
    <>
      <OperationsBinMap
        busy={busy}
        map={map}
        selectedStationId={selected?.station_id}
        onRefresh={onRefresh}
        onSelectStation={(station) => setSelectedId(station.station_id)}
      />
      <aside className="side-panel operations-side-panel">
        <div>
          <span className="eyebrow">Trạm gần bạn</span>
          <h2>{selected?.name ?? "Chọn trạm"}</h2>
        </div>
        {selected ? <StationDetail station={selected} /> : <div className="empty-state">Chưa có trạm để hiển thị.</div>}
      </aside>
    </>
  );
}

export function UserAlertsScreen({ alerts }: UserAlertsScreenProps) {
  return (
    <div className="panel operations-wide-panel">
      <div className="panel-toolbar">
        <div>
          <span className="eyebrow">Cảnh báo</span>
          <h2>Các vấn đề cần theo dõi</h2>
        </div>
        <AlertTriangle size={22} />
      </div>
      <AlertList alerts={alerts?.alerts ?? []} />
    </div>
  );
}

export function UserScheduleScreen({ busy, collectOnly, schedules, onCompleteCollection }: UserScheduleScreenProps) {
  const rows = useMemo(() => {
    const all = schedules?.schedules ?? [];
    if (!collectOnly) {
      return all;
    }
    return all.filter((schedule) => schedule.state === "due_today" || schedule.state === "overdue" || schedule.state === "scheduled");
  }, [collectOnly, schedules]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  return (
    <div className="panel operations-wide-panel">
      <div className="panel-toolbar">
        <div>
          <span className="eyebrow">{collectOnly ? "Thu gom" : "Lịch thu gom"}</span>
          <h2>{collectOnly ? "Đánh dấu đã thu gom" : "Lịch trạm được phân công"}</h2>
        </div>
        <CalendarCheck size={22} />
      </div>
      <div className="operations-list">
        {rows.map((schedule) => (
          <article className="operations-list-card schedule-card" key={schedule.schedule_id}>
            <div className="operations-row-title">
              <Flag size={18} />
              <div>
                <strong>{schedule.station_name}</strong>
                <small>
                  {schedule.scheduled_date} - {schedule.window_start || "--"} đến {schedule.window_end || "--"}
                </small>
              </div>
            </div>
            <span className={schedule.state === "completed" ? "status-chip" : schedule.state === "overdue" ? "status-chip danger" : "status-chip warning"}>
              {schedule.state}
            </span>
            {collectOnly ? (
              <div className="operations-inline-form">
                <input
                  onChange={(event) => setNotes({ ...notes, [schedule.schedule_id]: event.target.value })}
                  placeholder="Ghi chú thu gom"
                  value={notes[schedule.schedule_id] ?? ""}
                />
                <button
                  className="primary-button compact-button"
                  disabled={busy || schedule.state === "completed"}
                  onClick={() => onCompleteCollection(schedule.schedule_id, notes[schedule.schedule_id] ?? "")}
                  type="button"
                >
                  <CheckCircle2 size={16} />
                  <span>Đã thu gom</span>
                </button>
              </div>
            ) : null}
          </article>
        ))}
        {rows.length === 0 ? <div className="empty-state">Không có lịch thu gom trong phạm vi hiện tại.</div> : null}
      </div>
    </div>
  );
}

export function UserDeviceIssueScreen({ busy, map, onReportIssue }: UserDeviceIssueScreenProps) {
  const [form, setForm] = useState<DeviceIssueCreatePayload>({
    description: "",
    issue_type: "sensor_problem",
    severity: "warning",
    station_id: map?.stations[0]?.station_id ?? ""
  });

  useEffect(() => {
    setForm((current) => ({
      ...current,
      station_id: current.station_id || map?.stations[0]?.station_id || ""
    }));
  }, [map?.stations]);

  const selectedStation = map?.stations.find((station) => station.station_id === form.station_id);

  return (
    <div className="panel operations-wide-panel">
      <div className="panel-toolbar">
        <div>
          <span className="eyebrow">Báo lỗi</span>
          <h2>Báo lỗi thiết bị hoặc tọa độ</h2>
        </div>
        <AlertTriangle size={22} />
      </div>
      <div className="form-grid two-col">
        <label>
          Trạm
          <select onChange={(event) => setForm({ ...form, station_id: event.target.value })} value={form.station_id}>
            {(map?.stations ?? []).map((station) => (
              <option key={station.station_id} value={station.station_id}>
                {station.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Bin
          <select onChange={(event) => setForm({ ...form, bin_id: event.target.value })} value={form.bin_id ?? ""}>
            <option value="">Toàn trạm</option>
            {(selectedStation?.bins ?? []).map((bin) => (
              <option key={bin.bin_id} value={bin.bin_id}>
                {bin.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Loại lỗi
          <select onChange={(event) => setForm({ ...form, issue_type: event.target.value })} value={form.issue_type}>
            {issueTypes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Mức độ
          <select
            onChange={(event) => setForm({ ...form, severity: event.target.value as DeviceIssueCreatePayload["severity"] })}
            value={form.severity}
          >
            <option value="info">info</option>
            <option value="warning">warning</option>
            <option value="danger">danger</option>
          </select>
        </label>
        <label className="span-2">
          Mô tả
          <textarea
            onChange={(event) => setForm({ ...form, description: event.target.value })}
            placeholder="Mô tả lỗi nhìn thấy tại trạm"
            value={form.description}
          />
        </label>
      </div>
      <button
        className="primary-button"
        disabled={busy || !form.description.trim()}
        onClick={() => onReportIssue(form)}
        type="button"
      >
        <Save size={17} />
        <span>Gửi báo lỗi</span>
      </button>
    </div>
  );
}

function AlertList({
  alerts,
  busy = false,
  onPatchAlert
}: {
  alerts: AlertsResponse["alerts"];
  busy?: boolean;
  onPatchAlert?: (alertId: string, status: "open" | "acknowledged" | "resolved") => void;
}) {
  if (alerts.length === 0) {
    return <div className="empty-state">Chưa có cảnh báo mở.</div>;
  }
  return (
    <div className="operations-list">
      {alerts.map((alert) => (
        <article className="operations-list-card" key={alert.alert_id}>
          <div className="operations-row-title">
            <Bell size={18} />
            <div>
              <strong>{alert.title}</strong>
              <small>{alert.station_id || alert.device_id || "toàn hệ thống"} - {alert.created_at}</small>
            </div>
          </div>
          <span className={alert.severity === "danger" ? "status-chip danger" : alert.severity === "warning" ? "status-chip warning" : "status-chip"}>
            {alert.severity} / {alert.status}
          </span>
          <p>{alert.message}</p>
          {onPatchAlert ? (
            <div className="button-row">
              <button
                className="secondary-button compact-button"
                disabled={busy || alert.status === "acknowledged"}
                onClick={() => onPatchAlert(alert.alert_id, "acknowledged")}
                type="button"
              >
                <Edit3 size={15} />
                <span>Đã xem</span>
              </button>
              <button
                className="primary-button compact-button"
                disabled={busy || alert.status === "resolved"}
                onClick={() => onPatchAlert(alert.alert_id, "resolved")}
                type="button"
              >
                <CheckCircle2 size={15} />
                <span>Đã xử lý</span>
              </button>
            </div>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function ScheduleList({ compact, schedules }: { compact?: boolean; schedules: CollectionSchedule[] }) {
  if (schedules.length === 0) {
    return <div className="empty-state">Chưa có lịch thu gom.</div>;
  }
  return (
    <div className={compact ? "operations-list compact-list" : "operations-list"}>
      {schedules.map((schedule) => (
        <article className="operations-list-card" key={schedule.schedule_id}>
          <div className="operations-row-title">
            <CalendarCheck size={18} />
            <div>
              <strong>{schedule.station_name}</strong>
              <small>
                {schedule.scheduled_date} - {schedule.window_start || "--"} đến {schedule.window_end || "--"}
              </small>
            </div>
          </div>
          <span className={schedule.state === "completed" ? "status-chip" : schedule.state === "overdue" ? "status-chip danger" : "status-chip warning"}>
            {schedule.state}
          </span>
        </article>
      ))}
    </div>
  );
}

function StationDetail({ station }: { station: BinStation }) {
  return (
    <div className="operations-station-detail">
      <p>{station.address}</p>
      <div className="operations-mini-metrics">
        <span>
          <strong>{station.bins.length}</strong>
          <small>ngăn</small>
        </span>
        <span>
          <strong>{station.open_alert_total}</strong>
          <small>cảnh báo</small>
        </span>
        <span>
          <strong>{station.coordinate_verified ? "Có" : "Chưa"}</strong>
          <small>xác minh</small>
        </span>
      </div>
      <div className="operations-list compact-list">
        {station.bins.map((bin) => (
          <article className="operations-list-card" key={bin.bin_id}>
            <div className="operations-row-title">
              <MapPin size={16} />
              <div>
                <strong>{bin.label}</strong>
                <small>{bin.command}/bin{bin.bin_index} - đầy {bin.fill_percent}%</small>
              </div>
            </div>
            <span className={bin.status === "full" ? "status-chip danger" : bin.status === "warning" ? "status-chip warning" : "status-chip"}>
              {bin.status}
            </span>
          </article>
        ))}
      </div>
    </div>
  );
}

type StationFormState = {
  active: boolean;
  address: string;
  area: string;
  coordinate_verified: boolean;
  device_id: string;
  latitude: string;
  longitude: string;
  name: string;
  note: string;
  owner_username: string;
  station_id: string;
  status: string;
};

function CreateStationForm({
  busy,
  onCreate
}: {
  busy: boolean;
  onCreate: (payload: BinStationCreatePayload) => void;
}) {
  const [form, setForm] = useState<StationFormState>({
    active: true,
    address: "",
    area: "Thủ Đức",
    coordinate_verified: false,
    device_id: "",
    latitude: "",
    longitude: "",
    name: "",
    note: "",
    owner_username: "",
    station_id: "",
    status: "candidate"
  });
  return (
    <StationForm
      busy={busy}
      form={form}
      mode="create"
      onChange={setForm}
      onSubmit={() => onCreate(formToCreatePayload(form))}
    />
  );
}

function StationForm({
  busy,
  form,
  mode,
  onChange,
  onSubmit
}: {
  busy: boolean;
  form: StationFormState;
  mode: "create" | "patch";
  onChange: (value: StationFormState) => void;
  onSubmit: () => void;
}) {
  return (
    <div className="form-grid two-col">
      {mode === "create" ? (
        <label>
          Station ID
          <input onChange={(event) => onChange({ ...form, station_id: event.target.value })} value={form.station_id} />
        </label>
      ) : null}
      <label>
        Tên trạm
        <input onChange={(event) => onChange({ ...form, name: event.target.value })} value={form.name} />
      </label>
      <label>
        Khu vực
        <input onChange={(event) => onChange({ ...form, area: event.target.value })} value={form.area} />
      </label>
      <label className="span-2">
        Địa chỉ
        <input onChange={(event) => onChange({ ...form, address: event.target.value })} value={form.address} />
      </label>
      <label>
        Latitude
        <input onChange={(event) => onChange({ ...form, latitude: event.target.value })} value={form.latitude} />
      </label>
      <label>
        Longitude
        <input onChange={(event) => onChange({ ...form, longitude: event.target.value })} value={form.longitude} />
      </label>
      <label>
        Trạng thái
        <select onChange={(event) => onChange({ ...form, status: event.target.value })} value={form.status}>
          <option value="candidate">candidate</option>
          <option value="active">active</option>
          <option value="maintenance">maintenance</option>
          <option value="inactive">inactive</option>
        </select>
      </label>
      <label>
        User phụ trách
        <input onChange={(event) => onChange({ ...form, owner_username: event.target.value })} value={form.owner_username} />
      </label>
      <label>
        Device ID
        <input onChange={(event) => onChange({ ...form, device_id: event.target.value })} value={form.device_id} />
      </label>
      <label className="inline-check">
        <input
          checked={form.coordinate_verified}
          onChange={(event) => onChange({ ...form, coordinate_verified: event.target.checked })}
          type="checkbox"
        />
        Tọa độ đã xác minh
      </label>
      <label className="inline-check">
        <input checked={form.active} onChange={(event) => onChange({ ...form, active: event.target.checked })} type="checkbox" />
        Đang hoạt động
      </label>
      <label className="span-2">
        Ghi chú
        <textarea onChange={(event) => onChange({ ...form, note: event.target.value })} value={form.note} />
      </label>
      <button className="primary-button" disabled={busy || !form.name.trim()} onClick={onSubmit} type="button">
        <Save size={17} />
        <span>{mode === "create" ? "Tạo trạm" : "Lưu tọa độ"}</span>
      </button>
    </div>
  );
}

function stationToForm(station: BinStation | null): StationFormState {
  return {
    active: station?.active ?? true,
    address: station?.address ?? "",
    area: station?.area ?? "",
    coordinate_verified: station?.coordinate_verified ?? false,
    device_id: station?.device_id ?? "",
    latitude: typeof station?.latitude === "number" ? String(station.latitude) : "",
    longitude: typeof station?.longitude === "number" ? String(station.longitude) : "",
    name: station?.name ?? "",
    note: station?.note ?? "",
    owner_username: station?.owner_username ?? "",
    station_id: station?.station_id ?? "",
    status: station?.status ?? "candidate"
  };
}

function formToPayload(form: StationFormState): BinStationPatchPayload {
  return {
    active: form.active,
    address: form.address,
    area: form.area,
    coordinate_verified: form.coordinate_verified,
    device_id: form.device_id,
    latitude: parseCoordinate(form.latitude),
    longitude: parseCoordinate(form.longitude),
    name: form.name,
    note: form.note,
    owner_username: form.owner_username,
    status: form.status
  };
}

function formToCreatePayload(form: StationFormState): BinStationCreatePayload {
  return {
    ...formToPayload(form),
    name: form.name,
    station_id: form.station_id
  };
}

function parseCoordinate(value: string) {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
