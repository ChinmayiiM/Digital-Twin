import Card from '../Card'
import { pct } from '../../utils/format'

const hours = (x) => `${Number(x).toFixed(2)} h`

/** Re-run vs. original run of the same question - both calculated by the simulator. */
export default function LearningEffect({ effect }) {
  const changedPlans = effect.plan_changes.filter((p) => Math.abs(p.on_time_after - p.on_time_before) >= 0.005)
  return (
    <Card className="border-indigo-200">
      <p className="text-sm font-medium text-indigo-700">Re-run of scenario #{effect.previous_scenario_id}</p>
      <h2 className="mt-1 text-2xl font-bold text-slate-900">
        {effect.twin_changes.length ? 'Your Twin has changed' : 'Your Twin is unchanged'}
      </h2>
      <p className="mt-1 text-slate-600">{effect.message}</p>

      {effect.twin_changes.length > 0 && (
        <div className="mt-4">
          <p className="mb-1 text-sm font-semibold text-slate-800">Twin values used</p>
          <ul className="space-y-1 text-sm text-slate-700">
            {effect.twin_changes.map((t) => (
              <li key={t.label}>
                <strong>{t.label}:</strong> {t.before} → <span className="font-semibold text-indigo-700">{t.after}</span>
                {t.evidence_before !== t.evidence_after && (
                  <span className="text-slate-500"> (evidence {t.evidence_before} → {t.evidence_after})</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <p className="mb-1 text-sm font-semibold text-slate-800">Time your Twin expects each task to need</p>
          <ul className="space-y-1 text-sm text-slate-700">
            {effect.task_changes.map((t) => (
              <li key={t.task_id}>
                {t.title}: your estimate {t.estimated_after} h → Twin-adjusted {hours(t.adjusted_before)} →{' '}
                <span className="font-semibold text-indigo-700">{hours(t.adjusted_after)}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="mb-1 text-sm font-semibold text-slate-800">Chance to finish on time: previous → current</p>
          {changedPlans.length === 0 ? (
            <p className="text-sm text-slate-500">No on-time chance changed.</p>
          ) : (
            <ul className="space-y-1 text-sm text-slate-700">
              {changedPlans.map((p) => (
                <li key={`${p.plan_id}-${p.task_title}`}>
                  Plan {p.plan_id}, {p.task_title}: {pct(p.on_time_before)} →{' '}
                  <span className="font-semibold text-indigo-700">{pct(p.on_time_after)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <p className="mt-4 text-sm text-slate-700">
        <strong>Recommendation:</strong> {effect.previous_recommendation} →{' '}
        <strong>{effect.current_recommendation}</strong>
        {effect.recommendation_changed ? ' (changed)' : ' (unchanged)'}
      </p>
    </Card>
  )
}
