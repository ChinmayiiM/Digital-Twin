import Card from './Card'
import TraitChangeCard from './TraitChangeCard'
import { formatUtc } from '../utils/dates'

/** Digital Twin page: the latest learning updates from feedback (stored Twin snapshots). */
export default function TwinUpdatesCard({ updates }) {
  return (
    <Card title="Recent learning from feedback">
      {updates.length === 0 ? (
        <p className="text-sm text-slate-400">
          No feedback-based updates yet. Give feedback with an actual outcome on the What-If Simulator page.
        </p>
      ) : (
        <div className="space-y-5">
          {updates.map((u) => (
            <div key={u.snapshot_id}>
              <p className="mb-2 text-sm text-slate-600">
                <strong className="text-slate-800">{formatUtc(u.created_at)}</strong> - {u.reason}
              </p>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {u.changes.filter((c) => c.significant).map((c) => <TraitChangeCard key={c.trait_name} change={c} />)}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
