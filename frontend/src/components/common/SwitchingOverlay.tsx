export default function SwitchingOverlay() {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="rounded-lg border bg-surface px-6 py-4 shadow-lg">
        <span className="text-sm text-muted">Switching workspace…</span>
      </div>
    </div>
  );
}
