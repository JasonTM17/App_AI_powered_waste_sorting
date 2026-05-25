type SkeletonVariant = "dashboard" | "table" | "map" | "form" | "list" | "card-grid";

interface PageSkeletonProps {
  variant: SkeletonVariant;
}

function SkeletonBlock({
  height,
  width,
  rounded = 8,
}: {
  height: number | string;
  width?: number | string;
  rounded?: number;
}) {
  return (
    <div
      style={{
        animation: "pulse 2s infinite",
        background: "#e2e8f0",
        borderRadius: rounded,
        height,
        width: width ?? "100%",
      }}
    />
  );
}

function DashboardSkeleton() {
  return (
    <div style={{ display: "grid", gap: 18, padding: "24px 0" }}>
      <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(3, minmax(0, 1fr))" }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            style={{
              background: "#ffffff",
              border: "1px solid #e2e8f0",
              borderRadius: 14,
              display: "grid",
              gap: 10,
              minHeight: 132,
              padding: 18,
            }}
          >
            <SkeletonBlock height={16} width="50%" />
            <SkeletonBlock height={28} width="70%" />
            <SkeletonBlock height={14} width="40%" />
          </div>
        ))}
      </div>
      <SkeletonBlock height={220} />
      <SkeletonBlock height={140} />
    </div>
  );
}

function TableSkeleton() {
  return (
    <div style={{ display: "grid", gap: 12, padding: "24px 0" }}>
      <div style={{ display: "flex", gap: 12 }}>
        <SkeletonBlock height={40} width={200} />
        <SkeletonBlock height={40} width={120} />
      </div>
      <SkeletonBlock height={320} />
    </div>
  );
}

function MapSkeleton() {
  return (
    <div style={{ display: "grid", gap: 14, padding: "24px 0" }}>
      <SkeletonBlock height={48} width={300} />
      <SkeletonBlock height="clamp(360px, 52vh, 620px)" />
    </div>
  );
}

function FormSkeleton() {
  return (
    <div style={{ display: "grid", gap: 14, padding: "24px 0", maxWidth: 640 }}>
      <SkeletonBlock height={36} width={200} />
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} style={{ display: "grid", gap: 6 }}>
          <SkeletonBlock height={14} width={100} />
          <SkeletonBlock height={40} />
        </div>
      ))}
      <SkeletonBlock height={40} width={140} />
    </div>
  );
}

function ListSkeleton() {
  return (
    <div style={{ display: "grid", gap: 12, padding: "24px 0" }}>
      <SkeletonBlock height={40} width={260} />
      {Array.from({ length: 5 }).map((_, i) => (
        <SkeletonBlock key={i} height={64} />
      ))}
    </div>
  );
}

function CardGridSkeleton() {
  return (
    <div style={{ display: "grid", gap: 14, padding: "24px 0" }}>
      <SkeletonBlock height={40} width={260} />
      <div
        style={{
          display: "grid",
          gap: 14,
          gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        }}
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonBlock key={i} height={180} />
        ))}
      </div>
    </div>
  );
}

const skeletonMap: Record<SkeletonVariant, () => React.ReactNode> = {
  dashboard: DashboardSkeleton,
  table: TableSkeleton,
  map: MapSkeleton,
  form: FormSkeleton,
  list: ListSkeleton,
  "card-grid": CardGridSkeleton,
};

export function PageSkeleton({ variant }: PageSkeletonProps) {
  const Skeleton = skeletonMap[variant];
  return <Skeleton />;
}
