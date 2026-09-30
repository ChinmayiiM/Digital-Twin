import Card from './Card'
import ConfidenceMeter from './ConfidenceMeter'

/** Shows one trait exactly as the backend reports it. Nothing is calculated or invented here. */
export default function TwinTraitCard({ trait }) {
  const known = trait.sufficient_evidence
  return (
    <Card title={trait.display_name}>
      <p className={known ? 'text-xl font-semibold text-slate-900' : 'text-lg font-medium text-slate-400'}>
        {trait.display_value}
      </p>
      <div className="mt-4">
        <ConfidenceMeter confidence={trait.confidence} evidenceCount={trait.evidence_count} />
      </div>
      <div className="mt-4 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">
        <p className="mb-0.5 text-xs font-semibold text-slate-500">
          {known ? 'Why TwinMate thinks this:' : 'Why there is no value yet:'}
        </p>
        <p>{trait.description}</p>
      </div>
    </Card>
  )
}
