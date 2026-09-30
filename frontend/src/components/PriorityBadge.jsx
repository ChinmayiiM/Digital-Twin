const STYLES = {
  high: 'bg-red-50 text-red-700 border-red-200',
  medium: 'bg-amber-50 text-amber-700 border-amber-200',
  low: 'bg-slate-100 text-slate-600 border-slate-200',
}

export default function PriorityBadge({ priority }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${STYLES[priority] || STYLES.low}`}>
      {priority}
    </span>
  )
}
