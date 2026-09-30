import Card from './Card'
import { formatUtc } from '../utils/dates'

function describe(o) {
  const ctx = o.context || {}
  switch (o.observation_type) {
    case 'task_estimation':
      return `Estimated ${ctx.estimated_hours}h → actual ${o.observed_value}h`
    case 'focus_session':
      return `${o.observed_value} minute focus session`
    case 'working_time':
      return `${ctx.time_period} productivity ${Math.round(o.observed_value * 100)}%`
    case 'delay':
      return o.observed_value === 0 ? 'Finished on time' : `Finished ${o.observed_value}h after the deadline`
    case 'task_order':
      return `Finished a ${ctx.chosen?.estimated_hours}h ${ctx.chosen?.priority}-priority task before ${ctx.remaining?.length ?? 0} other task(s)`
    default:
      return o.observation_type
  }
}

export default function EvidenceLog({ observations, total }) {
  return (
    <Card title={`Evidence log (latest ${observations.length} of ${total})`}>
      {observations.length === 0 ? (
        <p className="text-sm text-slate-400">No observations stored yet.</p>
      ) : (
        <ul className="divide-y divide-slate-100 text-sm">
          {observations.map((o) => (
            <li key={o.id} className="flex items-center justify-between gap-3 py-2">
              <span className="text-slate-700">{describe(o)}</span>
              <span className="flex shrink-0 items-center gap-2 text-xs text-slate-400">
                {o.source === 'demo' && (
                  <span className="rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 font-medium text-amber-700">Synthetic demo</span>
                )}
                {o.source === 'feedback' && (
                  <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700">From feedback</span>
                )}
                {formatUtc(o.created_at)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
