/** Confidence = how much evidence TwinMate has (evidence / 10), not statistical certainty. */
export default function ConfidenceMeter({ confidence, evidenceCount }) {
  const pct = Math.round(confidence * 100)
  return (
    <div className="grid grid-cols-2 gap-4 text-sm">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Confidence</p>
        <p className="font-semibold text-slate-800">{pct}%</p>
        <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100">
          <div className="h-1.5 rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
        </div>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Evidence</p>
        <p className="font-semibold text-slate-800">
          {evidenceCount} observation{evidenceCount === 1 ? '' : 's'}
        </p>
      </div>
    </div>
  )
}
