import Card from './Card'
import ConfidenceMeter from './ConfidenceMeter'
import ProductivityChart from './ProductivityChart'

/** Productivity pattern = three backend traits (morning / afternoon / evening) in one card. */
export default function ProductivityCard({ traits, statedPreference }) {
  const totalEvidence = traits.reduce((sum, t) => sum + t.evidence_count, 0)
  const anyKnown = traits.some((t) => t.sufficient_evidence)

  return (
    <Card title="Productivity Pattern" className="md:col-span-2">
      {anyKnown ? (
        <ProductivityChart traits={traits} />
      ) : (
        <p className="text-lg font-medium text-slate-400">Not enough evidence yet</p>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
        {traits.map((t) => (
          <div key={t.trait_name} className="rounded-lg border border-slate-100 p-3">
            <p className="text-sm font-semibold text-slate-700">{t.display_name.replace(' productivity', '')}</p>
            <p className={`mb-3 text-lg font-semibold ${t.sufficient_evidence ? 'text-slate-900' : 'text-slate-400'}`}>
              {t.display_value}
            </p>
            <ConfidenceMeter confidence={t.confidence} evidenceCount={t.evidence_count} />
          </div>
        ))}
      </div>

      <p className="mt-3 text-sm text-slate-500">Total evidence: {totalEvidence} observation{totalEvidence === 1 ? '' : 's'}</p>

      <div className="mt-3 space-y-1 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
        <p className="text-xs font-semibold text-slate-500">Why TwinMate thinks this:</p>
        {traits.map((t) => (
          <p key={t.trait_name}>
            <strong className="text-slate-700">{t.display_name.replace(' productivity', '')}:</strong> {t.description}
          </p>
        ))}
      </div>

      {statedPreference && (
        <p className="mt-3 text-xs text-slate-400">
          You told us you prefer <strong>{statedPreference.preferred_working_time}</strong>. That is a stated
          preference from your profile - it is kept separate from the observed values above.
        </p>
      )}
    </Card>
  )
}
