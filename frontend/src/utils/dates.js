// Deadlines travel as naive local strings like "2026-10-01T18:00:00" (no timezone),
// and JavaScript parses those as local time, so what the user picks is what they see.

const pad = (n) => String(n).padStart(2, '0')

/** <input type="datetime-local"> value ("2026-10-01T18:00") -> API value ("2026-10-01T18:00:00") */
export function toApiDateTime(inputValue) {
  if (!inputValue) return null
  return inputValue.length === 16 ? `${inputValue}:00` : inputValue
}

/** A datetime-local value N days from today at the given hour (used by the demo button). */
export function inputValueDaysFromNow(days, hour = 18) {
  const d = new Date()
  d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(hour)}:00`
}

export function parseDeadline(value) {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** "2026-10-01T18:00:00" -> "Oct 1, 6:00 PM" */
export function formatDeadline(value) {
  const d = parseDeadline(value)
  if (!d) return 'No deadline'
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}

/** "Due tomorrow", "Due in 3 days", "Overdue by 1 day" ... based on calendar days. */
export function dueLabel(value) {
  const d = parseDeadline(value)
  if (!d) return 'No deadline'
  const startOf = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate())
  const days = Math.round((startOf(d) - startOf(new Date())) / 86400000)
  if (days < 0) return `Overdue by ${-days} day${days === -1 ? '' : 's'}`
  if (days === 0) return 'Due today'
  if (days === 1) return 'Due tomorrow'
  return `Due in ${days} days`
}

export const isOverdue = (value, status) => {
  const d = parseDeadline(value)
  return Boolean(d) && status !== 'completed' && d < new Date()
}

/** created_at / last_updated come from the server in UTC without a "Z"; show them in local time. */
export function formatUtc(value) {
  if (!value) return '—'
  const iso = /[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value.replace(' ', 'T')}Z`
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
}
