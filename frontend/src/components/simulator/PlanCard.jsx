import Card from '../Card'
import { pct, RISK_STYLES } from '../../utils/format'

/** One simulated plan: what it does, its typical schedule, and its headline numbers. */
export default function PlanCard({ plan, colourOf, recommended }) {
  const hoursPerDay = Math.max(...plan.schedule.map((d) => d.blocks.reduce((s, b) => s + b.hours, 0) + d.idle_hours + d.switch_hours), 1)

  return (
    <Card className={recommended ? 'ring-2 ring-indigo-500' : ''}>
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-semibold text-slate-900">Plan {plan.id}: {plan.name}</h3>
        {plan.is_user_proposal && (
          <span className="rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">Your idea</span>
        )}
      </div>
      <p className="mt-1 text-sm text-slate-500">{plan.description}</p>

      <div className="mt-4 space-y-2">
        <p className="text-xs font-medium text-slate-500">Typical schedule (all values at your Twin's learned averages)</p>
        {plan.schedule.map((day) => (
          <div key={day.date} className="flex items-center gap-3 text-xs">
            <span className="w-24 shrink-0 text-slate-500">{day.label}</span>
            <div className="flex h-4 flex-1 overflow-hidden rounded bg-slate-100" title="Grey = unused time">
              {day.blocks.map((b) => (
                <div
                  key={b.task_id}
                  style={{ width: `${(b.hours / hoursPerDay) * 100}%`, background: colourOf(b.task_id) }}
                  title={`${b.task_title}: ${b.hours} h`}
                />
              ))}
              {day.switch_hours > 0 && (
                <div style={{ width: `${(day.switch_hours / hoursPerDay) * 100}%` }} className="bg-slate-400" title={`Task switching: ${day.switch_hours} h`} />
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div>
          <p className="text-xs text-slate-500">Expected overall progress</p>
          <p className="font-semibold text-slate-900">{pct(plan.overall_expected)}</p>
          <p className="text-xs text-slate-400">likely {pct(plan.overall_low)} - {pct(plan.overall_high)}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500">Worst deadline risk</p>
          <span className={`inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${RISK_STYLES[plan.risk_label]}`}>
            {plan.risk_label}
          </span>
        </div>
      </div>

      <ul className="mt-3 space-y-1 text-sm text-slate-600">
        {plan.tasks.map((t) => (
          <li key={t.task_id} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: colourOf(t.task_id) }} />
            <span className="min-w-0">
              {t.title}: needs ≈{t.adjusted_required_hours} h, gets {t.hours_before_deadline} h before its deadline ·{' '}
              {pct(t.on_time_probability)} on time
            </span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
