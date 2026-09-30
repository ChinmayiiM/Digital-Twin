import { useState } from 'react'
import Button from './Button'
import Card from './Card'
import Input, { Select } from './Input'
import { createObservation, getErrorMessage } from '../services/api'

const TYPES = [
  { value: 'task_estimation', label: 'Task: estimated vs. actual time' },
  { value: 'focus_session', label: 'Focus session length' },
  { value: 'working_time', label: 'Productivity at a time of day' },
  { value: 'delay', label: 'Task delay (after deadline)' },
]
const PERIODS = [
  { value: 'morning', label: 'Morning' },
  { value: 'afternoon', label: 'Afternoon' },
  { value: 'evening', label: 'Evening' },
]

const positive = (v) => v !== '' && !Number.isNaN(Number(v)) && Number(v) > 0

export default function AddObservationForm({ userId, onAdded }) {
  const [type, setType] = useState('task_estimation')
  const [estimated, setEstimated] = useState('')
  const [actual, setActual] = useState('')
  const [minutes, setMinutes] = useState('')
  const [period, setPeriod] = useState('morning')
  const [percent, setPercent] = useState('')
  const [lateHours, setLateHours] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  function buildPayload() {
    const base = { user_id: Number(userId), source: 'user' }
    if (type === 'task_estimation') {
      if (!positive(estimated)) return 'Estimated hours must be greater than 0.'
      if (!positive(actual)) return 'Actual hours must be greater than 0.'
      return { ...base, observation_type: type, observed_value: Number(actual), context: { estimated_hours: Number(estimated) } }
    }
    if (type === 'focus_session') {
      if (!positive(minutes) || Number(minutes) > 600) return 'Focus minutes must be between 1 and 600.'
      return { ...base, observation_type: type, observed_value: Number(minutes), context: {} }
    }
    if (type === 'working_time') {
      if (percent === '' || Number(percent) < 0 || Number(percent) > 100) return 'Productivity must be between 0 and 100.'
      return { ...base, observation_type: type, observed_value: Number(percent) / 100, context: { time_period: period } }
    }
    if (lateHours === '' || Number(lateHours) < 0) return 'Hours late must be 0 or more (0 = on time).'
    return { ...base, observation_type: 'delay', observed_value: Number(lateHours), context: {} }
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    setSuccess('')
    const payload = buildPayload()
    if (typeof payload === 'string') return setError(payload)
    setBusy(true)
    try {
      await createObservation(payload)
      setEstimated(''); setActual(''); setMinutes(''); setPercent(''); setLateHours('')
      setSuccess('Observation saved. Click "Update Twin" to let the Pattern Analyzer learn from it.')
      await onAdded()
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to save observation. Please try again.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Add an observation">
      <form onSubmit={submit} className="space-y-3">
        <Select label="What did you observe?" options={TYPES} value={type} onChange={(e) => setType(e.target.value)} />

        {type === 'task_estimation' && (
          <div className="grid grid-cols-2 gap-3">
            <Input label="Estimated hours" type="number" min="0" step="0.5" value={estimated} onChange={(e) => setEstimated(e.target.value)} />
            <Input label="Actual hours" type="number" min="0" step="0.5" value={actual} onChange={(e) => setActual(e.target.value)} />
          </div>
        )}
        {type === 'focus_session' && (
          <Input label="Minutes you stayed focused" type="number" min="0" max="600" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
        )}
        {type === 'working_time' && (
          <div className="grid grid-cols-2 gap-3">
            <Select label="Time of day" options={PERIODS} value={period} onChange={(e) => setPeriod(e.target.value)} />
            <Input label="Productivity (0-100%)" type="number" min="0" max="100" value={percent} onChange={(e) => setPercent(e.target.value)} />
          </div>
        )}
        {type === 'delay' && (
          <Input label="Hours finished after the deadline" hint="Use 0 if it was on time." type="number" min="0" step="0.5" value={lateHours} onChange={(e) => setLateHours(e.target.value)} />
        )}

        {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        {success && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{success}</p>}
        <Button type="submit" variant="secondary" loading={busy}>Save observation</Button>
      </form>
    </Card>
  )
}
