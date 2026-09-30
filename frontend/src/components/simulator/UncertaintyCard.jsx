import Card from '../Card'
import { pct } from '../../utils/format'

const LABEL_STYLE = { Low: 'text-red-600', Moderate: 'text-amber-600', High: 'text-emerald-600' }

/** Prediction (not observed behaviour): expected outcome, likely range and how much evidence backs it. */
export default function UncertaintyCard({ confidence, planLabel, settings }) {
  const c = confidence
  return (
    <Card title="Prediction confidence">
      {c.limited_evidence && (
        <p role="status" className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          Your Twin has limited evidence for this prediction.
        </p>
      )}
      <p className={`text-2xl font-bold ${LABEL_STYLE[c.label]}`}>{c.label}</p>
      <p className="text-xs text-slate-400">Twin confidence {pct(c.score)} from {c.evidence_count} observation{c.evidence_count === 1 ? '' : 's'}</p>

      <div className="mt-4">
        <p className="text-sm text-slate-600">
          Expected overall progress for {planLabel}: <strong className="text-slate-900">{pct(c.expected_outcome)}</strong>
        </p>
        <p className="text-sm text-slate-600">
          Likely range: <strong className="text-slate-900">{pct(c.outcome_low)} - {pct(c.outcome_high)}</strong>
          <span className="text-xs text-slate-400"> (10th-90th percentile of {settings.simulations_per_plan.toLocaleString()} simulations)</span>
        </p>
        <div className="relative mt-3 h-2 rounded-full bg-slate-100" aria-hidden="true">
          <div
            className="absolute h-2 rounded-full bg-indigo-200"
            style={{ left: pct(c.outcome_low), width: `${Math.max(1, (c.outcome_high - c.outcome_low) * 100)}%` }}
          />
          <div className="absolute -top-1 h-4 w-1 rounded bg-indigo-600" style={{ left: `calc(${pct(c.expected_outcome)} - 2px)` }} />
        </div>
        <div className="mt-1 flex justify-between text-xs text-slate-400"><span>0%</span><span>100%</span></div>
      </div>

      <p className="mt-4 text-sm text-slate-600"><strong className="text-slate-700">Why:</strong> {c.message}</p>
      <p className="mt-2 text-xs text-slate-400">
        This is a simulation estimate from your Twin, not observed behavior and not a guarantee.
      </p>
    </Card>
  )
}
