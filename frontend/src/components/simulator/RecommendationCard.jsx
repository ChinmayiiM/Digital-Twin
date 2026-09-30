import Card from '../Card'

/** The calculated recommendation (Python score), its reasons, trade-offs and the explanation text. */
export default function RecommendationCard({ recommendation, explanation }) {
  const r = recommendation
  return (
    <Card className="border-indigo-200 bg-indigo-50/40">
      <p className="text-sm font-medium text-indigo-700">{r.no_clear_preference ? 'Result' : 'Recommended plan'}</p>
      <h2 className="mt-1 text-2xl font-bold text-slate-900">{r.headline}</h2>

      <div className="mt-4 rounded-lg border border-slate-200 bg-white px-4 py-3">
        <p className="text-slate-800">{explanation.text}</p>
        <p className="mt-2 text-xs text-slate-400">{explanation.label}</p>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-5 md:grid-cols-2">
        <div>
          <p className="mb-1 font-semibold text-slate-800">{r.no_clear_preference ? 'Why there is no recommendation' : 'Why TwinMate recommends this'}</p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {r.reasons.map((x) => <li key={x}>{x}</li>)}
          </ul>
        </div>
        <div>
          <p className="mb-1 font-semibold text-slate-800">Trade-offs</p>
          {r.trade_offs.length === 0 ? (
            <p className="text-sm text-slate-500">No significant trade-offs found in the simulation.</p>
          ) : (
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              {r.trade_offs.map((x) => <li key={x}>{x}</li>)}
            </ul>
          )}
        </div>
      </div>

      <details className="mt-5 text-sm">
        <summary className="cursor-pointer font-medium text-indigo-700">How the recommendation score was calculated</summary>
        <p className="mt-2 text-xs text-slate-500">{r.formula}. The top two scores must differ by at least 0.03, otherwise no plan is recommended.</p>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full min-w-[480px] text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="py-1 pr-2">Plan</th><th className="px-2">Progress</th><th className="px-2">On-time</th>
                <th className="px-2">Risk penalty</th><th className="px-2">Overload penalty</th><th className="px-2">Habit bonus</th>
                <th className="px-2">Score</th>
              </tr>
            </thead>
            <tbody>
              {r.scores.map((s) => (
                <tr key={s.plan_id} className="border-b border-slate-100 text-slate-700">
                  <td className="py-1 pr-2 font-medium">{s.plan_id}</td>
                  <td className="px-2">{s.progress.toFixed(2)}</td><td className="px-2">{s.on_time.toFixed(2)}</td>
                  <td className="px-2">-{s.risk_penalty.toFixed(2)}</td><td className="px-2">-{s.overload_penalty.toFixed(2)}</td>
                  <td className="px-2">+{s.habit_bonus.toFixed(2)}</td><td className="px-2 font-semibold">{s.total.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </Card>
  )
}
