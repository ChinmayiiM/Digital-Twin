import useHealthCheck from '../hooks/useHealthCheck'

const UI = {
  checking: { label: 'Checking backend...', dot: 'bg-amber-400 animate-pulse', box: 'bg-amber-50 text-amber-700 border-amber-200' },
  connected: { label: 'Backend Connected', dot: 'bg-emerald-500', box: 'bg-emerald-50 text-emerald-700 border-emerald-200' },
  failed: { label: 'Backend Connection Failed', dot: 'bg-red-500', box: 'bg-red-50 text-red-700 border-red-200' },
}

/** Small pill driven by a real GET /api/health request (kept from Phase 1). */
export default function BackendStatus() {
  const { status, recheck } = useHealthCheck()
  const ui = UI[status]
  return (
    <button
      onClick={recheck}
      title="Click to re-check"
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium ${ui.box}`}
    >
      <span className={`h-2 w-2 rounded-full ${ui.dot}`} />
      {ui.label}
    </button>
  )
}
