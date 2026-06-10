"use client";

import { AlertTriangle, CheckCircle2, LocateFixed, MapPin, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { DivIcon, DivIconOptions, LatLngExpression, Map as LeafletMap, Marker } from "leaflet";

import type { BinMapResponse, BinStation } from "@/lib/agent";

type OperationsBinMapProps = {
  map: BinMapResponse | null;
  busy: boolean;
  selectedStationId?: string;
  onRefresh: () => void;
  onSelectStation?: (station: BinStation) => void;
};

export function OperationsBinMap({
  busy,
  map,
  selectedStationId,
  onRefresh,
  onSelectStation
}: OperationsBinMapProps) {
  const mapElementRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersRef = useRef<Marker[]>([]);
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
      if (!instance) {
        return;
      }
      if (!currentMap) {
        return;
      }
      const centerLatitude = currentMap.center.latitude;
      const centerLongitude = currentMap.center.longitude;
      markersRef.current.forEach((marker) => marker.remove());
      markersRef.current = [];

      stations.forEach((station) => {
        const icon = stationIcon(leaflet.divIcon, station, station.station_id === selectedStationId);
        const marker = leaflet
          .marker([station.latitude ?? centerLatitude, station.longitude ?? centerLongitude], { icon })
          .bindPopup(`<strong>${escapeHtml(station.name)}</strong><br/>${escapeHtml(station.address)}`)
          .on("click", () => onSelectStation?.(station))
          .addTo(instance);
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
  }, [map, mapReady, onSelectStation, selectedStationId, stations]);

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
      markersRef.current.forEach((marker) => marker.remove());
      mapRef.current?.remove();
      mapRef.current = null;
      markersRef.current = [];
    },
    []
  );

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
  return divIcon({
    className: "",
    html: `<span class="operations-map-marker ${tone} ${selected ? "selected" : ""}">${station.bins.length}</span>`,
    iconAnchor: [15, 15],
    iconSize: [30, 30]
  });
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
