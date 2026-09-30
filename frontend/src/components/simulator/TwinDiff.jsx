import Button from '../Button'
import Card from '../Card'
import TraitChangeCard from '../TraitChangeCard'

/** Result of POST /api/feedback: what was recorded, what TwinMate learned, and the Twin Diff. */
export default function TwinDiff({ feedback, onRerun, rerunning }) {
  const learned = feedback.updated
  const blocked = feedback.learning_blocked // Phase 6: learning paused or history permission off
  const changes = feedback.changes.filter((c) => c.significant)

  return (
    <Card>
      <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-800">
        Your feedback has been recorded.
      </p>

      <h2 className="mt-4 text-2xl font-bold text-slate-900">
        {learned ? 'Your Twin learned from this feedback' : blocked ? 'Your Twin was not updated' : 'No significant trait changes'}
      </h2>
      {blocked && <p className="mt-1 text-amber-700">{blocked}</p>}
      {!learned && !blocked && (
        <p className="mt-1 text-slate-600">
          Your feedback was recorded, but there is not enough new behavioral evidence to meaningfully change a trait yet.
        </p>
      )}

      <ol className="mt-4 space-y-1 text-sm">
        {feedback.learning_steps.map((s) => (
          <li key={s.step} className="flex gap-2">
            <span className="text-indigo-600">✓</span>
            <span><strong className="text-slate-800">{s.title}</strong> <span className="text-slate-500">- {s.detail}</span></span>
          </li>
        ))}
      </ol>

      {changes.length > 0 && (
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          {changes.map((c) => <TraitChangeCard key={c.trait_name} change={c} />)}
        </div>
      )}

      <details className="mt-5 text-sm" open={!learned}>
        <summary className="cursor-pointer font-medium text-indigo-700">How TwinMate read your feedback</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
          {feedback.interpretation.notes.map((n) => <li key={n}>{n}</li>)}
        </ul>
      </details>

      <div className="mt-6 flex flex-col items-center gap-2 border-t border-slate-100 pt-5">
        <Button onClick={onRerun} loading={rerunning} className="px-6 py-3 text-base">Re-run This Scenario</Button>
        <p className="text-xs text-slate-500">Runs the same question again with your {learned ? 'updated' : 'current'} Twin. Nothing is reused from the old result.</p>
      </div>
    </Card>
  )
}
