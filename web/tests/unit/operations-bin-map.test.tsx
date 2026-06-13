import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OperationsBinMap } from "@/components/operations-bin-map";
import type { BinMapResponse } from "@/lib/agent";
import { renderWithProviders } from "../helpers/render-with-providers";
import { DEFAULT_BIN_MAP_RESPONSE } from "../helpers/mock-agent-fetch";

const leafletMock = {
  map: vi.fn(() => ({
    setView: vi.fn(),
    remove: vi.fn(),
    fitBounds: vi.fn(),
    panTo: vi.fn()
  })),
  marker: vi.fn(() => ({
    bindPopup: vi.fn().mockReturnThis(),
    on: vi.fn().mockReturnThis(),
    addTo: vi.fn(),
    remove: vi.fn(),
    getLatLng: vi.fn(() => ({ lat: 10.85, lng: 106.75 }))
  })),
  tileLayer: vi.fn(() => ({
    on: vi.fn().mockReturnThis(),
    addTo: vi.fn()
  })),
  divIcon: vi.fn(() => ({})),
  latLngBounds: vi.fn(() => ({
    pad: vi.fn(() => ({})),
    extend: vi.fn()
  }))
};

vi.mock("leaflet", () => ({
  ...leafletMock,
  default: leafletMock
}));

vi.mock("leaflet.markercluster", () => ({
  markerClusterGroup: vi.fn(() => ({
    addTo: vi.fn(),
    addLayer: vi.fn(),
    remove: vi.fn()
  })),
  default: {
    markerClusterGroup: vi.fn(() => ({
      addTo: vi.fn(),
      addLayer: vi.fn(),
      remove: vi.fn()
    }))
  }
}));

vi.mock("react-dom/client", () => ({
  createRoot: vi.fn(() => ({
    render: vi.fn(),
    unmount: vi.fn()
  }))
}));

function setup(overrides?: {
  busy?: boolean;
  map?: BinMapResponse | null;
  refreshMeta?: {
    lastUpdatedAt: string;
    isRefreshing: boolean;
    refreshError: string;
  };
  onRefresh?: () => void;
}) {
  const props = {
    busy: false,
    map: DEFAULT_BIN_MAP_RESPONSE,
    onRefresh: vi.fn(),
    ...overrides
  };
  const result = renderWithProviders(<OperationsBinMap {...props} />);
  return { props, ...result };
}

describe("OperationsBinMap", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders map card with title when map data is provided", () => {
    setup();
    expect(screen.getByText("Bản đồ thùng rác Thủ Đức")).toBeInTheDocument();
  });

  it("renders empty state when no map data", () => {
    setup({ map: null });
    expect(screen.getByText("Chưa có dữ liệu bản đồ")).toBeInTheDocument();
  });

  it("renders fallback station list with clickable rows", () => {
    setup();
    expect(screen.getByText("Trạm test 1")).toBeInTheDocument();
  });

  it("calls onRefresh when refresh button is clicked", async () => {
    const { props } = setup();
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: /làm mới/i }));
    expect(props.onRefresh).toHaveBeenCalledTimes(1);
  });

  it("renders user realtime refresh status when provided", () => {
    setup({
      refreshMeta: {
        lastUpdatedAt: new Date().toISOString(),
        isRefreshing: false,
        refreshError: ""
      }
    });

    expect(screen.getByTestId("map-refresh-status")).toHaveTextContent(/Vừa cập nhật|Đang cập nhật/);
  });

  it("toggles map focus mode when expand button is clicked", async () => {
    setup();
    const user = userEvent.setup();

    await user.click(screen.getByTitle("Mở rộng bản đồ"));
    expect(screen.getByTitle("Thu nhỏ bản đồ")).toBeInTheDocument();
  });
});
