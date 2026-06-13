"use client";

import { AlertTriangle, CheckCircle2, LocateFixed, MapPin, Maximize2, Minimize2, RefreshCcw } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import type { DivIcon, DivIconOptions, LatLngExpression, LayerGroup, Map as LeafletMap, Marker } from "leaflet";

import type { BinMapResponse, BinStation, OperationBin } from "@/lib/agent";

const CLUSTER_THRESHOLD = 30;
const OSM_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

type OperationsBinMapProps = {
  map: BinMapResponse | null;
  busy: boolean;
  editable?: boolean;
  selectedStationId?: string;
  refreshMeta?: {
    lastUpdatedAt: string;
    isRefreshing: boolean;
    refreshError: string;
  };
  onInteraction?: () => void;
  onMoveStation?: (stationId: string, latitude: number, longitude: number) => void;
  onRefresh: () => void;
  onSelectStation?: (station: BinStation) => void;
};

import { ErrorBoundary } from "@/components/error-boundary";

export function OperationsBinMap(props: OperationsBinMapProps) {
  return (
    <ErrorBoundary fallback={<div className="operations-map-card empty-state"><AlertTriangle size={28}/><strong>Lỗi tải bản đồ</strong><span>Vui lòng thử tải lại trang hoặc kiểm tra kết nối mạng.</span></div>}>
      <OperationsBinMapInner {...props} />
    </ErrorBoundary>
  );
}

function OperationsBinMapInner({
  busy,
  editable = false,
  map,
  onInteraction,
  onMoveStation,
  refreshMeta,
  selectedStationId,
  onRefresh,
  onSelectStation
}: OperationsBinMapProps) {
  const mapElementRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<LeafletMap | null>(null);
  const markersMapRef = useRef<Map<string, Marker>>(new Map());
  const popupRootsMapRef = useRef<Map<string, Root>>(new Map());
  const clusterLayerRef = useRef<LayerGroup | null>(null);
  const fittedStationsKeyRef = useRef("");
  const [tileFailed, setTileFailed] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [renderedMarkerCount, setRenderedMarkerCount] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);

  const stations = useMemo(
    () => (map?.stations ?? []).filter((station) => hasCoordinates(station)),
    [map?.stations]
  );
  const missingCoordinateCount = Math.max(0, (map?.stations.length ?? 0) - stations.length);

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
      setTileFailed(false);
      const center: LatLngExpression = [map.center.latitude, map.center.longitude];
      const instance = leaflet.map(mapElementRef.current, {
        attributionControl: true,
        center,
        dragging: !shouldReduceMapGestures(),
        inertiaDeceleration: 5200,
        inertiaMaxSpeed: 1200,
        scrollWheelZoom: false,
        wheelDebounceTime: 80,
        wheelPxPerZoomLevel: 180,
        zoom: map.center.zoom,
        zoomControl: true,
        zoomDelta: 0.5,
        zoomSnap: 0.5
      });
      leaflet
        .tileLayer(OSM_TILE_URL, {
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
    if (!isExpanded) {
      document.body.classList.remove("map-expanded-lock");
      return;
    }
    document.body.classList.add("map-expanded-lock");
    return () => {
      document.body.classList.remove("map-expanded-lock");
    };
  }, [isExpanded]);

  useEffect(() => {
    if (!isExpanded) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsExpanded(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isExpanded]);

  useEffect(() => {
    if (!mapReady || !mapRef.current) {
      return;
    }
    const reduceGestures = shouldReduceMapGestures();
    const allowDirectMapGestures = isExpanded || !reduceGestures;
    setMapHandlerEnabled(mapRef.current.dragging, allowDirectMapGestures);
    setMapHandlerEnabled(mapRef.current.touchZoom, allowDirectMapGestures);
    setMapHandlerEnabled(mapRef.current.scrollWheelZoom, isExpanded);
    const raf = window.requestAnimationFrame(() => {
      mapRef.current?.invalidateSize?.({ pan: false, debounceMoveend: true });
    });
    return () => window.cancelAnimationFrame(raf);
  }, [isExpanded, mapReady]);

  useEffect(() => {
    const element = mapElementRef.current;
    if (!mapReady || !element || isExpanded) {
      return;
    }
    let lastTouchY = 0;
    const scrollPage = (deltaY: number) => {
      window.scrollBy({ top: deltaY, left: 0, behavior: "auto" });
    };
    const handleWheel = (event: WheelEvent) => {
      onInteraction?.();
      scrollPage(event.deltaY);
      event.preventDefault();
      event.stopImmediatePropagation();
    };
    const handleTouchStart = (event: TouchEvent) => {
      onInteraction?.();
      lastTouchY = event.touches[0]?.clientY ?? 0;
    };
    const handleTouchMove = (event: TouchEvent) => {
      onInteraction?.();
      const currentY = event.touches[0]?.clientY ?? lastTouchY;
      const deltaY = lastTouchY - currentY;
      lastTouchY = currentY;
      if (Math.abs(deltaY) > 1) {
        scrollPage(deltaY);
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };
    element.addEventListener("wheel", handleWheel, { capture: true, passive: false });
    element.addEventListener("touchstart", handleTouchStart, { capture: true, passive: true });
    element.addEventListener("touchmove", handleTouchMove, { capture: true, passive: false });
    return () => {
      element.removeEventListener("wheel", handleWheel, { capture: true });
      element.removeEventListener("touchstart", handleTouchStart, { capture: true });
      element.removeEventListener("touchmove", handleTouchMove, { capture: true });
    };
  }, [isExpanded, mapReady, onInteraction]);

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

      const prevHadCluster = !!clusterLayerRef.current;
      const needCluster = stations.length > CLUSTER_THRESHOLD;

      if (prevHadCluster !== needCluster) {
        markersMapRef.current.forEach((marker) => {
          if (clusterLayerRef.current) {
            clusterLayerRef.current.removeLayer(marker);
          } else {
            marker.remove();
          }
        });
        clusterLayerRef.current?.remove();
        clusterLayerRef.current = null;
      }

      let clusterLayer = clusterLayerRef.current;
      if (needCluster && !clusterLayer) {
        if (typeof window !== "undefined") {
          (window as any).L = leaflet;
        }
        await import("leaflet.markercluster");
        clusterLayer = leaflet.markerClusterGroup({
          chunkedLoading: true,
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true
        });
        clusterLayer.addTo(instance);
        clusterLayerRef.current = clusterLayer;
      }

      const currentStationIds = new Set(stations.map((s) => s.station_id));

      markersMapRef.current.forEach((marker, stationId) => {
        if (!currentStationIds.has(stationId)) {
          if (clusterLayer) {
            clusterLayer.removeLayer(marker);
          } else {
            marker.remove();
          }
          markersMapRef.current.delete(stationId);

          const root = popupRootsMapRef.current.get(stationId);
          if (root) {
            deferUnmountRoot(root);
            popupRootsMapRef.current.delete(stationId);
          }
        }
      });

      stations.forEach((station) => {
        const icon = stationIcon(leaflet.divIcon, station, station.station_id === selectedStationId);
        const lat = station.latitude ?? centerLatitude;
        const lng = station.longitude ?? centerLongitude;

        let marker = markersMapRef.current.get(station.station_id);
        let popupRoot = popupRootsMapRef.current.get(station.station_id);

        if (marker) {
          marker.setLatLng([lat, lng]);
          marker.setIcon(icon);

          if (editable) {
            marker.dragging?.enable();
          } else {
            marker.dragging?.disable();
          }

          marker.off("click");
          marker.on("click", () => {
            onInteraction?.();
            onSelectStation?.(station);
            marker.openPopup();
          });

          if (editable && onMoveStation) {
            marker.off("dragend");
            marker.on("dragend", () => {
              const position = marker.getLatLng();
              onMoveStation(station.station_id, position.lat, position.lng);
            });
          }

          if (popupRoot) {
            popupRoot.render(<StationPopupCard station={station} />);
          }

          if (prevHadCluster !== needCluster) {
            if (clusterLayer) {
              clusterLayer.addLayer(marker);
            } else {
              marker.addTo(instance);
            }
          }
        } else {
          const popupElement = document.createElement("div");
          popupElement.className = "operations-map-popup-root";
          const newPopupRoot = createRoot(popupElement);
          newPopupRoot.render(<StationPopupCard station={station} />);
          popupRootsMapRef.current.set(station.station_id, newPopupRoot);

          const newMarker = leaflet
            .marker([lat, lng], {
              draggable: editable,
              icon
            })
            .bindPopup(popupElement)
            .on("click", () => {
              onInteraction?.();
              onSelectStation?.(station);
              newMarker.openPopup();
            });

          if (editable && onMoveStation) {
            newMarker.on("dragend", () => {
              const position = newMarker.getLatLng();
              onMoveStation(station.station_id, position.lat, position.lng);
            });
          }

          if (clusterLayer) {
            clusterLayer.addLayer(newMarker);
          } else {
            newMarker.addTo(instance);
          }
          markersMapRef.current.set(station.station_id, newMarker);
        }
      });

      const fitKey = stationFitKey(currentMap, stations);
      if (fittedStationsKeyRef.current !== fitKey && stations.length > 1) {
        const bounds = leaflet.latLngBounds(
          stations.map((station) => [station.latitude ?? centerLatitude, station.longitude ?? centerLongitude])
        );
        instance.fitBounds(bounds.pad(0.16), { animate: false, maxZoom: 14 });
        fittedStationsKeyRef.current = fitKey;
      } else if (fittedStationsKeyRef.current !== fitKey && stations.length === 1) {
        const station = stations[0];
        instance.setView(
          [station.latitude ?? centerLatitude, station.longitude ?? centerLongitude],
          14,
          { animate: false }
        );
        fittedStationsKeyRef.current = fitKey;
      }
      setRenderedMarkerCount(markersMapRef.current.size);
    }

    void renderMarkers();
  }, [editable, map, mapReady, onInteraction, onMoveStation, onSelectStation, selectedStationId, stations]);

  useEffect(() => {
    if (!mapReady || !mapRef.current || !map || !selectedStationId) {
      return;
    }
    const station = stations.find((item) => item.station_id === selectedStationId);
    if (station) {
      const selectedMarker = markersMapRef.current.get(station.station_id);
      selectedMarker?.openPopup();
      mapRef.current.panTo(
        [station.latitude ?? map.center.latitude, station.longitude ?? map.center.longitude],
        { animate: false }
      );
    }
  }, [map, mapReady, selectedStationId, stations]);

  useEffect(
    () => () => {
      cleanupMarkerLayers();
      if (mapRef.current) {
        try {
          mapRef.current.remove();
        } catch (e) {}
        mapRef.current = null;
      }
    },
    []
  );

  useEffect(() => {
    if (map) {
      return;
    }
    cleanupMarkerLayers();
    setRenderedMarkerCount(0);
    setMapReady(false);
    setTileFailed(false);
    setIsExpanded(false);
    fittedStationsKeyRef.current = "";
    if (mapRef.current) {
      try {
        mapRef.current.remove();
      } catch (e) {}
      mapRef.current = null;
    }
  }, [map]);

  function cleanupMarkerLayers() {
    popupRootsMapRef.current.forEach((root) => deferUnmountRoot(root));
    popupRootsMapRef.current.clear();
    markersMapRef.current.forEach((marker) => marker.remove());
    markersMapRef.current.clear();
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
    <div className={isExpanded ? "operations-map-card is-expanded" : "operations-map-card"}>
      <div className="panel-toolbar">
        <div>
          <span className="eyebrow">OpenStreetMap</span>
          <h2>Bản đồ thùng rác Thủ Đức</h2>
        </div>
        <div className="map-toolbar-actions">
          <button
            className="icon-button"
            onClick={() => setIsExpanded((value) => !value)}
            title={isExpanded ? "Thu nhỏ bản đồ" : "Mở rộng bản đồ"}
            type="button"
          >
            {isExpanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
            <span>{isExpanded ? "Thu nhỏ" : "Mở rộng"}</span>
          </button>
          <button className="icon-button" disabled={busy} onClick={onRefresh} title="Làm mới bản đồ" type="button">
            <RefreshCcw size={17} />
            <span>Làm mới</span>
          </button>
        </div>
      </div>
      <div className="operations-map-status-row" aria-label="Trạng thái dữ liệu bản đồ">
        <span className="status-chip" data-testid="map-station-count">
          {map.stations.length} trạm
        </span>
        <span className={mapReady ? "status-chip" : "status-chip warning"} data-testid="map-marker-count">
          {renderedMarkerCount}/{stations.length} marker
        </span>
        <span className={missingCoordinateCount ? "status-chip warning" : "status-chip"} data-testid="map-coordinate-count">
          {missingCoordinateCount ? `${missingCoordinateCount} thiếu tọa độ` : "Tọa độ sẵn sàng"}
        </span>
        {refreshMeta ? (
          <span
            className={
              refreshMeta.refreshError
                ? "status-chip danger"
                : refreshMeta.isRefreshing
                  ? "status-chip warning"
                  : "status-chip"
            }
            data-testid="map-refresh-status"
          >
            {refreshLabel(refreshMeta)}
          </span>
        ) : null}
      </div>
      <div className="operations-map-wrapper">
        <div
          aria-label="Bản đồ OpenStreetMap hiển thị các trạm thùng rác"
          className="operations-map-frame"
          data-gesture-mode={isExpanded ? "map" : "page-scroll"}
          ref={mapElementRef}
        />
        {busy && (
          <div className="operations-map-spinner-overlay" data-testid="map-spinner">
            <div className="operations-map-spinner" />
          </div>
        )}
      </div>
      {tileFailed ? (
        <div className="alert compact-alert">
          <AlertTriangle size={16} />
          <span>Tile bản đồ chưa tải được. Danh sách fallback bên dưới vẫn dùng được.</span>
        </div>
      ) : null}
      {editable ? <p className="helper-text">Kéo marker để cập nhật vị trí, hệ thống sẽ lưu ngay vào DB.</p> : null}
      {missingCoordinateCount ? (
        <div className="alert compact-alert">
          <LocateFixed size={16} />
          <span>
            {missingCoordinateCount} trạm chưa có tọa độ hợp lệ. Danh sách fallback vẫn dùng được, marker chỉ hiển thị cho trạm có tọa độ.
          </span>
        </div>
      ) : null}
      {!tileFailed && mapReady && stations.length > 0 && renderedMarkerCount === 0 ? (
        <div className="alert compact-alert">
          <AlertTriangle size={16} />
          <span>Marker đang được dựng. Nếu thông báo này không mất, bấm Làm mới bản đồ.</span>
        </div>
      ) : null}
      <div className="operations-map-list" data-testid="bin-map-fallback-list">
        {map.stations.map((station) => (
          <button
            aria-label={`Chọn ${station.name}`}
            className={station.station_id === selectedStationId ? "operations-station-row active" : "operations-station-row"}
            key={station.station_id}
            onClick={() => {
              onInteraction?.();
              onSelectStation?.(station);
            }}
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

function deferUnmountRoot(root: Root) {
  if (typeof window === "undefined") {
    root.unmount();
    return;
  }
  window.setTimeout(() => root.unmount(), 0);
}

function shouldReduceMapGestures() {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(max-width: 760px), (pointer: coarse)").matches;
}

function setMapHandlerEnabled(
  handler: { enable?: () => void; disable?: () => void } | undefined,
  enabled: boolean
) {
  const action = enabled ? handler?.enable : handler?.disable;
  if (typeof action === "function") {
    action.call(handler);
  }
}

function refreshLabel(refreshMeta: NonNullable<OperationsBinMapProps["refreshMeta"]>) {
  if (refreshMeta.refreshError) {
    return "Mất kết nối realtime";
  }
  if (refreshMeta.isRefreshing) {
    return "Đang cập nhật";
  }
  if (!refreshMeta.lastUpdatedAt) {
    return "Chờ dữ liệu realtime";
  }
  const updatedAt = Date.parse(refreshMeta.lastUpdatedAt);
  if (!Number.isFinite(updatedAt)) {
    return "Vừa cập nhật";
  }
  const ageSeconds = Math.max(0, Math.round((Date.now() - updatedAt) / 1000));
  if (ageSeconds < 15) {
    return "Vừa cập nhật";
  }
  if (ageSeconds < 60) {
    return `${ageSeconds}s trước`;
  }
  return "Dữ liệu cũ";
}

function hasCoordinates(station: BinStation) {
  return Number.isFinite(station.latitude) && Number.isFinite(station.longitude);
}

function stationFitKey(map: BinMapResponse, stations: BinStation[]) {
  const stationKey = stations
    .map((station) => `${station.station_id}:${station.latitude ?? ""},${station.longitude ?? ""}`)
    .join("|");
  return `${map.center.latitude},${map.center.longitude},${map.center.zoom}|${stationKey}`;
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
