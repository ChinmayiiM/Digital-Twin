import Card from '../Card'
import ConfidenceMeter from '../ConfidenceMeter'

const SOURCE = {
  profile: { text: 'You told us', style: 'bg-slate-100 text-slate-600 border-slate-200' },
  twin: { text: 'Learned by your Twin', style: 'bg-indigo-50 text-indigo-700 border-indigo-200' },
  fallback: { text: 'Neutral assumption', style: 'bg-amber-50 text-amber-700 border-amber-200' },
  not_permitted: { text: 'Permission off', style: 'bg-slate-100 text-slate-500 border-slate-200' },
}

/** Exactly which profile values and Twin traits the simulation used - straight from the backend. */
export default function TwinDataUsed({ items }) {
  return (
    <Card title="Twin data used in this simulation">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className="rounded-lg border border-slate-100 p-3">
            <p className="text-sm font-medium text-slate-600">{item.label}</p>
            <p className={`mt-0.5 font-semibold ${['fallback', 'not_permitted'].includes(item.source) ? 'text-slate-400' : 'text-slate-900'}`}>{item.value}</p>
            <span className={`mt-1 inline-block rounded-full border px-2 py-0.5 text-xs font-medium ${SOURCE[item.source].style}`}>
              {SOURCE[item.source].text}
            </span>
            <p className="mt-1 mb-2 text-xs text-slate-400">Used for {item.used_for}</p>
            {['twin', 'fallback'].includes(item.source) && (
              <ConfidenceMeter confidence={item.confidence ?? 0} evidenceCount={item.evidence_count ?? 0} />
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}
