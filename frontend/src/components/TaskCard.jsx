import { dueLabel, formatDeadline, isOverdue } from '../utils/dates'
import PriorityBadge from './PriorityBadge'

export const STATUS_OPTIONS = [
  { value: 'pending', label: 'Pending' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'completed', label: 'Completed' },
]

/**
 * Shows one task. Pass onStatusChange / onDelete to show the management controls
 * (dashboard task list); leave them out for a read-only card (onboarding, deadlines).
 */
export default function TaskCard({ task, goalTitle, onStatusChange, onDelete, onRemove, busy = false }) {
  const overdue = isOverdue(task.deadline, task.status)
  const done = task.status === 'completed'

  return (
    <div className="rounded-xl border border-slate-200 bg-white px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={`font-medium ${done ? 'text-slate-400 line-through' : 'text-slate-900'}`}>{task.title}</p>
          {goalTitle && <p className="text-xs text-indigo-600">Goal: {goalTitle}</p>}
        </div>
        <PriorityBadge priority={task.priority} />
      </div>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
        <span className={overdue ? 'font-medium text-red-600' : ''}>{dueLabel(task.deadline)}</span>
        <span>{formatDeadline(task.deadline)}</span>
        <span>{task.estimated_hours}h estimated</span>
      </div>

      {(onStatusChange || onDelete || onRemove) && (
        <div className="mt-3 flex items-center justify-between gap-3">
          {onStatusChange ? (
            <select
              value={task.status}
              disabled={busy}
              onChange={(e) => onStatusChange(task, e.target.value)}
              className="rounded-lg border border-slate-300 bg-white px-2 py-1 text-sm text-slate-700 focus:border-indigo-500 focus:outline-none disabled:opacity-50"
              aria-label={`Status of ${task.title}`}
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          ) : (
            <span />
          )}
          {onDelete && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onDelete(task)}
              className="text-sm font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
            >
              Delete
            </button>
          )}
          {onRemove && (
            <button type="button" onClick={onRemove} className="text-xs font-medium text-slate-400 hover:text-red-600">
              Remove
            </button>
          )}
        </div>
      )}
    </div>
  )
}
