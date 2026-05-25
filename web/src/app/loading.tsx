export default function RootLoading() {
  return (
    <div
      style={{
        alignItems: "center",
        display: "flex",
        justifyContent: "center",
        minHeight: "100dvh",
        background: "#f7f9fb",
      }}
    >
      <div
        style={{
          animation: "pulse 2s infinite",
          background: "#e2e8f0",
          borderRadius: 12,
          height: 200,
          maxWidth: 480,
          width: "100%",
        }}
      />
    </div>
  );
}
