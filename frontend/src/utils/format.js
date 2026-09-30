// Display helpers for the What-If simulator. They only FORMAT numbers the backend calculated.

export const pct = (x) => `${Math.round((x ?? 0) * 100)}%`

// One colour per task, used the same way in schedules and charts.
const TASK_COLOURS = ['#6366f1', '#f59e0b', '#10b981', '#0ea5e9', '#f43f5e', '#8b5cf6']
export const taskColour = (index) => TASK_COLOURS[index % TASK_COLOURS.length]

export const RISK_STYLES = {
  Low: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  Moderate: 'bg-amber-50 text-amber-700 border-amber-200',
  High: 'bg-red-50 text-red-700 border-red-200',
}
