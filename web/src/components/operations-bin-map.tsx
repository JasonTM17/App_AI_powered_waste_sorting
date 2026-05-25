"use client";

import { AlertTriangle, CheckCircle2, LocateFixed, MapPin, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import type { DivIcon, DivIconOptions, LatLngExpression, LayerGroup, Map as LeafletMap, Marker } from "leaflet";

import type { BinMapResponse, BinStation, OperationBin } from "@/lib/agent";

const CLUSTER_THRESHOLD = 30;

type OperationsBinMapProps = {
  map: BinMapResponse | null;
  busy: boolean;
  editable?: boolean;
  selectedStationId?: string;
  onMoveStation?: (stationId: string, latitude: number, longitude: number) => void;
  onRefresh: () => void;
  onSelectStation?: (station: BinStation) => void;
};

export function OperationsBinMap({
  busy,
  editable = false,
  map,
  onMoveStation,
  selectedStationId,
  onRefresh,
  onSelectStation
}: OperationsBinMapProps) {
  const mapElementRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
  const popupRootsRef = useRef<Root[]>([]);
  const clusterLayerRef = useRef<LayerGroup | null>(null);
  const [tileFailed, setTileFailed] = useState(false);
  const [mapReady, setMapReady] = useState(false);

  const stations = useMemo(
    () => (map?.stations ?? []).filter((station) => hasCoordinates(station)),
    [map?.stations]
  );

  useEffect(() => {
    let cancelled = false;

    async function setupMap() {
      if (!mapElementRef.current || !map || mapRef.current) {
        return;
      }
      const leaflet = await import("leaflet");
      if (cancelled || !mapElementRef.current) {
        return;
      }
      const center: LatLngExpression = [map.center.latitude, map.center.longitude];
      const instance = leaflet.map(mapElementRef.current, {
        attributionControl: true,
        center,
        zoom: map.center.zoom,
        zoomControl: true
      });
      leaflet
        .tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "&copy; OpenStreetMap contributors",
          maxZoom: 19
        })
        .on("tileerror", () => setTileFailed(true))
        .addTo(instance);
      mapRef.current = instance;
      setMapReady(true);
    }

    void setupMap();
    return () => {
      cancelled = true;
    };
  }, [map]);

  useEffect(() => {
    if (!mapReady || !mapRef.current || !map) {
      return;
    }

    async function renderMarkers() {
      const leaflet = await import("leaflet");
      const instance = mapRef.current;
      const currentMap = map;
      if (!instance || !currentMap) {
        return;
      }
      const centerLatitude = currentMap.center.latitude;
      const centerLongitude = currentMap.center.longitude;
      cleanupMarkerLayers();
      let clusterLayer: LayerGroup | null = null;
      if (stations.length > CLUSTER_THRESHOLD) {
        await import("leaflet.markercluster");
        clusterLayer = leaflet.markerClusterGroup({
          chunkedLoading: true,
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true
        });
        clusterLayer.addTo(instance);
        clusterLayerRef.current = clusterLayer;
      }

      stations.forEach((station) => {
        const icon = stationIcon(leaflet.divIcon, station, station.station_id === selectedStationId);
        const popupElement = document.createElement("div");
        popupElement.className = "operations-map-popup-root";
        const popupRoot = createRoot(popupElement);
        popupRoot.render(<StationPopupCard station={station} />);
        popupRootsRef.current.push(popupRoot);
        const marker = leaflet
          .marker([station.latitude ?? centerLatitude, station.longitude ?? centerLongitude], {
            draggable: editable,
            icon
          })
          .bindPopup(popupElement)
          .on("click", () => onSelectStation?.(station));
        if (editable && onMoveStation) {
          marker.on("dragend", () => {
            const position = marker.getLatLng();
            onMoveStation(station.station_id, position.lat, position.lng);
          });
        }
        if (clusterLayer) {
          clusterLayer.addLayer(marker);
        } else {
          marker.addTo(instance);
        }
        markersRef.current.push(marker);
      });

      if (stations.length > 1) {
        const bounds = leaflet.latLngBounds(
          stations.map((station) => [station.latitude ?? centerLatitude, station.longitude ?? centerLongitude])
        );
        instance.fitBounds(bounds.pad(0.16), { animate: false, maxZoom: 14 });
      }
    }

    void renderMarkers();
  }, [editable, map, mapReady, onMoveStation, onSelectStation, selectedStationId, stations]);

  useEffect(() => {
    if (!mapReady || !mapRef.current || !map || !selectedStationId) {
      return;
    }
    const station = stations.find((item) => item.station_id === selectedStationId);
    if (station) {
      mapRef.current.panTo([station.latitude ?? map.center.latitude, station.longitude ?? map.center.longitude]);
    }
  }, [map, mapReady, selectedStationId, stations]);

  useEffect(
    () => () => {
      cleanupMarkerLayers();
      mapRef.current?.remove();
      mapRef.current = null;
    },
    []
  );

  function cleanupMarkerLayers() {
    popupRootsRef.current.forEach((root) => root.unmount());
    popupRootsRef.current = [];
    markersRef.current.forEach((marker) => marker.remove());
    markersRef.current = [];
    clusterLayerRef.current?.remove();
    clusterLayerRef.current = null;
  }

  if (!map) {
    return (
      <div className="operations-map-card empty-state">
        <MapPin size={28} />
        <strong>Chưa có dữ liệu bản đồ</strong>
        <span>Agent local chưa trả về danh sách thùng rác.</span>
      </div>
    );
  }

  return (
    <div className="operations-map-card">
      <div className="panel-toolbar">
        <div>
          <span className="eyebrow">OpenStreetMap</span>
          <h2>Bản đồ thùng rác Thủ Đức</h2>
        </div>
        <button className="icon-button" disabled={busy} onClick={onRefresh} title="Làm mới bản đồ" type="button">
          <RefreshCcw size={17} />
          <span>Làm mới</span>
        </button>
      </div>
      <div className="operations-map-frame" ref={mapElementRef} />
      {tileFailed ? (
        <div className="alert compact-alert">
          <AlertTriangle size={16} />
          <span>Tile bản đồ chưa tải được. Danh sách fallback bên dưới vẫn dùng được.</span>
        </div>
      ) : null}
      {editable ? <p className="helper-text">Kéo marker để cập nhật vị trí, hệ thống sẽ lưu ngay vào DB.</p> : null}
      <div className="operations-map-list" data-testid="bin-map-fallback-list">
        {map.stations.map((station) => (
          <button
            className={station.station_id === selectedStationId ? "operations-station-row active" : "operations-station-row"}
            key={station.station_id}
            onClick={() => onSelectStation?.(station)}
            type="button"
          >
            <span className="station-status-icon">
              {station.coordinate_verified ? <CheckCircle2 size={16} /> : <LocateFixed size={16} />}
            </span>
            <span>
              <strong>{station.name}</strong>
              <small>
                {station.area} - {station.coordinate_verified ? "tọa độ đã xác minh" : "tọa độ ứng viên"}
                {station.owner_username ? ` - phụ trách ${station.owner_username}` : ""}
              </small>
            </span>
            <span className={station.open_alert_total > 0 ? "status-chip danger" : "status-chip"}>
              {station.open_alert_total} cảnh báo
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}

function hasCoordinates(station: BinStation) {
  return typeof station.latitude === "number" && typeof station.longitude === "number";
}

function stationIcon(divIcon: (options?: DivIconOptions) => DivIcon, station: BinStation, selected: boolean) {
  const tone = station.open_alert_total > 0 ? "danger" : station.coordinate_verified ? "verified" : "candidate";
  const label = station.open_alert_total > 0 ? "!" : String(Math.round(stationMaxFullness(station)));
  return divIcon({
    className: "",
    html: `<span class="operations-map-marker ${tone} ${selected ? "selected" : ""}" title="${escapeHtml(station.name)}">${label}</span>`,
    iconAnchor: [15, 15],
    iconSize: [30, 30]
  });
}

function StationPopupCard({ station }: { station: BinStation }) {
  return (
    <article className="operations-map-popup-card">
      <header>
        <span
          className={`popup-status-dot ${station.open_alert_total > 0 ? "danger" : station.coordinate_verified ? "ok" : "pending"}`}
        />
        <div>
          <strong>{station.name}</strong>
          <small>{station.address || station.area}</small>
        </div>
      </header>
      <dl className="popup-meta-grid">
        <div>
          <dt>Phụ trách</dt>
          <dd>{station.owner_username || "Chưa gán"}</dd>
        </div>
        <div>
          <dt>Tọa độ</dt>
          <dd>{station.coordinate_verified ? "Đã xác minh" : "Ứng viên"}</dd>
        </div>
        <div>
          <dt>Cảnh báo mở</dt>
          <dd>{station.open_alert_total}</dd>
        </div>
      </dl>
      <div className="popup-bin-list">
        {station.bins.map((bin) => (
          <BinFillRow bin={bin} key={`${station.station_id}-${bin.bin_id}`} />
        ))}
      </div>
      <p>{stationMaxFullness(station) >= 95 ? "Cần xử lý ngay." : "Đang theo dõi cảm biến."}</p>
    </article>
  );
}

function BinFillRow({ bin }: { bin: OperationBin }) {
  const percent = Math.max(0, Math.min(100, Number(bin.fill_percent ?? 0)));
  const tone = fillTone(percent);
  return (
    <div className="popup-bin-row">
      <span>{bin.command}</span>
      <div className="popup-fill-track" aria-label={`${bin.label || bin.command} đầy ${Math.round(percent)}%`}>
        <span className={`popup-fill-bar ${tone}`} style={{ width: `${percent}%` }} />
      </div>
      <strong>{Math.round(percent)}%</strong>
    </div>
  );
}

function stationMaxFullness(station: BinStation) {
  return Math.max(0, ...station.bins.map((bin) => Number(bin.fill_percent ?? 0)));
}

function fillTone(percent: number) {
  if (percent >= 95) {
    return "danger";
  }
  if (percent >= 80) {
    return "warning";
  }
  return "ok";
}

function escapeHtml(value: string) {
  return value.replace(/[&<>"']/g, (char) => {
    const map: Record<string, string> = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;"
    };
    return map[char] ?? char;
  });
}
