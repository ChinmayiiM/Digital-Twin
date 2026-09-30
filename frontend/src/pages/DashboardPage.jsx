import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import BackendStatus from '../components/BackendStatus'
import Button from '../components/Button'
import Card from '../components/Card'
import GoalCard from '../components/GoalCard'
import Navbar from '../components/Navbar'
import TaskCard from '../components/TaskCard'
import { deleteTask, getDashboard, getErrorMessage, getTwin, updateTask } from '../services/api'
import { clearCurrentUser, getCurrentUserId } from '../store/userStore'

function Stat({ label, value, sub }) {
  return (
    <Card>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-bold text-slate-900">{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </Card>
  )
}

/** Summary of the stored Twin. Every value shown here comes from GET /api/twin/{id}/traits. */
function TwinSummary({ twin }) {
  if (!twin) {
    return <p className="max-w-md text-sm text-slate-500">The Twin summary is not available right now.</p>
  }

  const n = twin.total_observations
  if (n === 0) {
    return (
      <div className="max-w-md">
        <p className="text-lg font-semibold text-slate-900">Your Twin is ready to learn.</p>
        <p className="mt-1 text-sm text-slate-500">
          Complete tasks and provide behavioral information to build more reliable personal patterns.
        </p>
        <p className="mt-2 text-sm text-slate-400">Evidence collected: 0 observations</p>
      </div>
    )
  }

  const insights = twin.traits
    .filter((t) => t.sufficient_evidence)
    .sort((a, b) => b.confidence - a.confidence)
    .slice(0, 3)

  return (
    <div className="max-w-md">
      <p className="text-lg font-semibold text-slate-900">
        Twin status: <span className="text-indigo-600">Learning from {n} observation{n === 1 ? '' : 's'}</span>
      </p>
      {twin.demo_observations > 0 && (
        <p className="text-xs text-amber-700">Includes {twin.demo_observations} synthetic demo observations.</p>
      )}
      {!twin.analyzed ? (
        <p className="mt-2 text-sm text-slate-500">
          Observations are stored but not analyzed yet. Open the Digital Twin page and click "Update Twin".
        </p>
      ) : insights.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">Not enough evidence yet for any reliable insight.</p>
      ) : (
        <div className="mt-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Top current insights</p>
          <ul className="mt-1 space-y-0.5 text-sm text-slate-700">
            {insights.map((t) => (
              <li key={t.trait_name}>
                <strong>{t.display_name}:</strong> {t.display_value}
              </li>
            ))}
          </ul>
        </div>
      )}
      {twin.observations_pending_analysis > 0 && (
        <p className="mt-2 text-xs font-medium text-indigo-700">
          {twin.observations_pending_analysis} new observation{twin.observations_pending_analysis === 1 ? '' : 's'} waiting to be analyzed.
        </p>
      )}
    </div>
  )
}

export default function DashboardPage() {
  const navigate = useNavigate()
  const userId = getCurrentUserId()

  const [data, setData] = useState(null)
  const [twin, setTwin] = useState(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busyTaskId, setBusyTaskId] = useState(null)

  const load = useCallback(async () => {
    setLoadError('')
    try {
      setData(await getDashboard(userId))
      // The Twin summary is optional: if it fails, the rest of the dashboard still works.
      try {
        setTwin(await getTwin(userId))
      } catch {
        setTwin(null)
      }
    } catch (err) {
      if (err.response?.status === 404) {
        clearCurrentUser()
        setLoadError('We could not find your Twin in the database (it may have been reset). Please create it again.')
        setData(null)
      } else {
        setLoadError(getErrorMessage(err, 'Unable to load your dashboard.'))
      }
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    if (!userId) {
      navigate('/', { replace: true })
      return
    }
    load()
  }, [userId, load, navigate])

  function startOver() {
    clearCurrentUser()
    navigate('/')
  }

  async function handleStatusChange(task, status) {
    setBusyTaskId(task.id)
    setActionError('')
    try {
      await updateTask(task.id, { status })
      await load()
    } catch (err) {
      setActionError(getErrorMessage(err, 'Unable to update task. Please try again.'))
    } finally {
      setBusyTaskId(null)
    }
  }

  async function handleDelete(task) {
    if (!window.confirm(`Delete "${task.title}"?`)) return
    setBusyTaskId(task.id)
    setActionError('')
    try {
      await deleteTask(task.id)
      await load()
    } catch (err) {
      setActionError(getErrorMessage(err, 'Unable to delete task. Please try again.'))
    } finally {
      setBusyTaskId(null)
    }
  }

  if (!userId) return null

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center text-slate-500">Loading your dashboard...</div>
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <main className="mx-auto max-w-md px-6 py-16 text-center">
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{loadError}</p>
          <div className="mt-4 flex justify-center gap-3">
            {getCurrentUserId() ? (
              <Button onClick={() => { setLoading(true); load() }}>Try again</Button>
            ) : (
              <Button onClick={() => navigate('/onboarding')}>Create My Twin</Button>
            )}
          </div>
        </main>
      </div>
    )
  }

  const goalTitles = Object.fromEntries(data.goals.map((g) => [g.id, g.title]))
  const knows = [
    ['Goals', data.goals_count > 0],
    ['Tasks', data.tasks_count > 0],
    ['Deadlines', data.tasks.some((t) => t.deadline)],
    ['Available hours', data.available_hours_per_day != null],
    ['Working preference', Boolean(data.preferred_working_time)],
  ]

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar userName={data.user.name} onStartOver={startOver} />
      <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <h1 className="text-2xl font-bold text-slate-900">Today's Overview</h1>

        {actionError && (
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <Stat label="Available Hours" value={data.available_hours_per_day ?? '—'} sub="per day" />
          <Stat label="Pending Tasks" value={data.pending_tasks} sub={`${data.in_progress_tasks} in progress · ${data.completed_tasks} completed`} />
          <Stat label="Goals" value={data.goals_count} />
        </div>

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Upcoming Deadlines">
            {data.upcoming_tasks.length === 0 ? (
              <p className="text-sm text-slate-400">No upcoming deadlines.</p>
            ) : (
              <div className="space-y-2">
                {data.upcoming_tasks.map((t) => (
                  <TaskCard key={t.id} task={t} goalTitle={goalTitles[t.goal_id]} />
                ))}
              </div>
            )}
          </Card>

          <div className="space-y-6">
            <Card title="Your Preferences">
              {data.available_hours_per_day != null ? (
                <div className="text-sm text-slate-700">
                  <p><span className="text-2xl font-bold text-slate-900">{data.available_hours_per_day}</span> hours/day</p>
                  <p className="mt-1 text-slate-500">Preferred time: <strong className="text-slate-800">{data.preferred_working_time}</strong></p>
                </div>
              ) : (
                <p className="text-sm text-slate-400">No preferences saved yet.</p>
              )}
            </Card>

            <Card title="Your Goals">
              {data.goals.length === 0 ? (
                <p className="text-sm text-slate-400">Add a goal to help TwinMate understand what you're working toward.</p>
              ) : (
                <div className="space-y-2">
                  {data.goals.map((g) => (
                    <GoalCard key={g.id} goal={g} />
                  ))}
                </div>
              )}
            </Card>
          </div>
        </div>

        <Card title={`All Tasks (${data.tasks_count})`}>
          {data.tasks.length === 0 ? (
            <p className="text-sm text-slate-400">You don't have any tasks yet.</p>
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {data.tasks.map((t) => (
                <TaskCard
                  key={t.id}
                  task={t}
                  goalTitle={goalTitles[t.goal_id]}
                  busy={busyTaskId === t.id}
                  onStatusChange={handleStatusChange}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </Card>

        <Card
          title="Your Digital Twin"
          action={<Button variant="secondary" onClick={() => navigate('/twin')}>View Digital Twin</Button>}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <TwinSummary twin={twin} />
            <div className="text-sm">
              <p className="mb-1 font-medium text-slate-700">Your Twin currently knows:</p>
              <ul className="space-y-0.5">
                {knows.map(([label, ok]) => (
                  <li key={label} className={ok ? 'text-emerald-600' : 'text-slate-400'}>
                    {ok ? '✓' : '○'} {label}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Card>

        <div className="flex justify-center pb-4"><BackendStatus /></div>
      </main>
    </div>
  )
}
