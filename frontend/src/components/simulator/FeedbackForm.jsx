import { useState } from 'react'
import Button from '../Button'
import Card from '../Card'
import Input, { Select, Textarea } from '../Input'
import { getErrorMessage, submitFeedback } from '../../services/api'

const RATINGS = [
  { value: 'helpful', label: 'Helpful' },
  { value: 'partially_helpful', label: 'Partially helpful' },
  { value: 'not_helpful', label: 'Not helpful' },
]
const REASONS = [
  { value: 'matched_situation', label: 'It matched my situation' },
  { value: 'estimate_accurate', label: 'The time estimate was accurate' },
  { value: 'task_took_longer', label: 'The task took longer than expected' },
  { value: 'task_faster', label: 'The task finished faster than expected' },
  { value: 'deadline_changed', label: 'The deadline changed' },
  { value: 'schedule_changed', label: 'My schedule changed' },
  { value: 'prefer_other_option', label: 'I prefer another option' },
  { value: 'other', label: 'Other' },
]
const YES_NO = [
  { value: '', label: 'Not specified' },
  { value: 'yes', label: 'Yes' },
  { value: 'no', label: 'No' },
]
const toBool = (v) => (v === '' ? null : v === 'yes')

/** Feedback on ONE stored scenario. Only measured outcomes (actual hours, deadline) can change the Twin. */
export default function FeedbackForm({ userId, result, onSubmitted }) {
  const tasks = result.plans[0].tasks
  const [rating, setRating] = useState('')
  const [reasons, setReasons] = useState([])
  const [taskId, setTaskId] = useState('')
  const [hours, setHours] = useState('')
  const [completed, setCompleted] = useState('')
  const [deadlineMet, setDeadlineMet] = useState('')
  const [hoursLate, setHoursLate] = useState('')
  const [notes, setNotes] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const toggle = (value) =>
    setReasons(reasons.includes(value) ? reasons.filter((r) => r !== value) : [...reasons, value])
  const showLate = completed === 'yes' && deadlineMet === 'no'
  const selectedTask = tasks.find((t) => String(t.task_id) === taskId)

  async function submit(e) {
    e.preventDefault()
    setError('')
    if (!rating) return setError('Please choose how helpful the recommendation was.')
    const outcomeGiven = hours !== '' || completed !== '' || deadlineMet !== ''
    if (outcomeGiven && !taskId) return setError('Choose which task the actual outcome is about.')
    if (hours !== '' && !(Number(hours) > 0)) return setError('Actual hours must be greater than 0 (leave it empty if unknown).')

    setBusy(true)
    try {
      const response = await submitFeedback({
        user_id: Number(userId),
        scenario_id: result.scenario_id,
        rating,
        reasons,
        task_id: taskId ? Number(taskId) : null,
        actual_hours: hours === '' ? null : Number(hours),
        completed: toBool(completed),
        deadline_met: toBool(deadlineMet),
        hours_late: showLate && hoursLate !== '' ? Number(hoursLate) : null,
        notes: notes.trim() || null,
      })
      onSubmitted(response)
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to save your feedback.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Feedback on this recommendation">
      <form onSubmit={submit} className="space-y-5">
        <div>
          <p className="mb-2 font-semibold text-slate-900">Was this recommendation helpful?</p>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Rating">
            {RATINGS.map((r) => (
              <button key={r.value} type="button" role="radio" aria-checked={rating === r.value}
                onClick={() => setRating(r.value)}
                className={`rounded-lg border px-4 py-2 text-sm font-medium transition ${
                  rating === r.value ? 'border-indigo-600 bg-indigo-600 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                }`}>
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="mb-2 font-semibold text-slate-900">Why? <span className="font-normal text-slate-400">(choose any)</span></p>
          <div className="flex flex-wrap gap-2">
            {REASONS.map((r) => (
              <button key={r.value} type="button" aria-pressed={reasons.includes(r.value)} onClick={() => toggle(r.value)}
                className={`rounded-full border px-3 py-1 text-sm transition ${
                  reasons.includes(r.value) ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
                }`}>
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 p-4">
          <p className="font-semibold text-slate-900">What actually happened? <span className="font-normal text-slate-400">(optional)</span></p>
          <p className="mb-3 text-xs text-slate-500">
            Only measured outcomes teach your Twin: the actual hours of a completed task, and whether it met its deadline.
          </p>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Select label="Task" value={taskId} onChange={(e) => setTaskId(e.target.value)}
              options={[{ value: '', label: 'No specific task' }, ...tasks.map((t) => ({ value: String(t.task_id), label: t.title }))]} />
            <Input label="Actual time taken (hours)" type="number" min="0" step="0.5" value={hours}
              onChange={(e) => setHours(e.target.value)}
              hint={selectedTask ? `Your estimate was ${selectedTask.estimated_hours} h` : undefined} />
            <Select label="Completed?" value={completed} onChange={(e) => setCompleted(e.target.value)} options={YES_NO} />
            <Select label="Deadline met?" value={deadlineMet} onChange={(e) => setDeadlineMet(e.target.value)} options={YES_NO} />
            {showLate && (
              <Input label="How many hours after the deadline?" type="number" min="0" step="0.5" value={hoursLate}
                onChange={(e) => setHoursLate(e.target.value)} />
            )}
          </div>
          <div className="mt-3">
            <Textarea label="Notes" maxLength={1000} value={notes} onChange={(e) => setNotes(e.target.value)}
              placeholder="I thought the assignment would take 5 hours, but it took much longer." />
          </div>
        </div>

        {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <div className="flex justify-end">
          <Button type="submit" loading={busy}>Submit feedback</Button>
        </div>
      </form>
    </Card>
  )
}
