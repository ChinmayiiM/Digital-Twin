import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import Card from '../Card'

/** Side-by-side metrics. No plan is marked "best" here - the recommendation is shown separately. */
export default function ComparisonTable({ comparison, plans }) {
  const ids = comparison.plan_ids

  // Chart: chance to finish each task on time, one bar per plan.
  const chartData = plans[0].tasks.map((t, k) => {
    const row = { task: t.title }
    plans.forEach((p) => { row[`Plan ${p.id}`] = Math.round(p.tasks[k].on_time_probability * 100) })
    return row
  })
  const barColours = ['#6366f1', '#94a3b8', '#0ea5e9']

  return (
    <Card title="Scenario comparison">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left">
              <th className="py-2 pr-3 font-medium text-slate-500">Metric</th>
              {ids.map((id) => (
                <th key={id} className="px-3 py-2 font-semibold text-slate-800">
                  Plan {id}
                  <span className="block text-xs font-normal text-slate-500">{comparison.plan_names[id]}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {comparison.rows.map((row) => (
              <tr key={row.metric} className="border-b border-slate-100">
                <td className="py-2 pr-3 text-slate-600">{row.metric}</td>
                {ids.map((id) => (
                  <td key={id} className="px-3 py-2 font-medium text-slate-900">{row.values[id]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="mt-6 mb-2 text-sm font-medium text-slate-700">Chance to finish each task on time (Monte Carlo)</p>
      <div style={{ width: '100%', height: 220 }}>
        <ResponsiveContainer>
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="task" tickLine={false} />
            <YAxis domain={[0, 100]} unit="%" tickLine={false} />
            <Tooltip formatter={(v) => `${v}%`} />
            <Legend />
            {plans.map((p, i) => (
              <Bar key={p.id} dataKey={`Plan ${p.id}`} fill={barColours[i % barColours.length]} radius={[4, 4, 0, 0]} maxBarSize={40} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        {ids.map((id) => (
          <div key={id} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
            <p className="mb-1 font-medium text-slate-700">Plan {id} trade-offs</p>
            <ul className="list-disc space-y-0.5 pl-4 text-slate-600">
              {comparison.trade_offs[id].map((t) => <li key={t}>{t}</li>)}
            </ul>
          </div>
        ))}
      </div>
    </Card>
  )
}
