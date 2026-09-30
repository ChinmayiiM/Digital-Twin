import Card from '../Card'

// The six steps the backend really runs (services/whatif_pipeline.py), in order.
const STEPS = [
  { step: 'understand', title: 'Understand your decision' },
  { step: 'plan', title: 'Generate possible plans' },
  { step: 'simulate', title: 'Simulate outcomes' },
  { step: 'compare', title: 'Compare scenarios' },
  { step: 'decide', title: 'Calculate recommendation' },
  { step: 'explain', title: 'Explain the result' },
]

/**
 * While the request runs we only show that the server is working (no fake ticks).
 * When the answer arrives, each step shows what the backend reported and how long it took.
 */
export default function WorkflowSteps({ running, workflow }) {
  const done = Object.fromEntries((workflow || []).map((w) => [w.step, w]))
  const stoppedEarly = workflow && workflow.length < STEPS.length

  return (
    <Card title="How TwinMate worked on this">
      <ol className="space-y-2">
        {STEPS.map((s, i) => {
          const result = done[s.step]
          const skipped = !running && stoppedEarly && !result
          return (
            <li key={s.step} className="flex items-start gap-3 text-sm">
              <span
                className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-semibold ${
                  result ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white text-slate-400'
                }`}
              >
                {result ? '✓' : i + 1}
              </span>
              <div className="min-w-0">
                <p className={result ? 'font-medium text-slate-900' : 'text-slate-400'}>{result ? result.title : s.title}</p>
                {result && (
                  <p className="text-xs text-slate-500">
                    {result.detail} <span className="text-slate-400">({result.duration_ms} ms)</span>
                  </p>
                )}
                {skipped && <p className="text-xs text-slate-400">Not run - see the message below.</p>}
              </div>
            </li>
          )
        })}
      </ol>
      {running && (
        <p className="mt-4 flex items-center gap-2 text-sm text-indigo-700">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
          Running on the TwinMate server...
        </p>
      )}
    </Card>
  )
}
