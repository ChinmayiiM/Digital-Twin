import PriorityBadge from './PriorityBadge'

export default function GoalCard({ goal, onRemove }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="min-w-0">
        <p className="font-medium text-slate-900">{goal.title}</p>
        {goal.description && <p className="mt-0.5 text-sm text-slate-500">{goal.description}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        <PriorityBadge priority={goal.priority} />
        {onRemove && (
          <button type="button" onClick={onRemove} className="text-xs font-medium text-slate-400 hover:text-red-600">
            Remove
          </button>
        )}
      </div>
    </div>
  )
}
