import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Card from '../components/Card'
import ConfirmDialog from '../components/ConfirmDialog'
import DataUsedPanel from '../components/DataUsedPanel'
import Navbar from '../components/Navbar'
import Toggle from '../components/Toggle'
import {
  exportTwin,
  forgetData,
  getAccessLogs,
  getDataUsed,
  getErrorMessage,
  getPrivacy,
  getUser,
  setLearningPaused,
  updatePermissions,
} from '../services/api'
import { clearCurrentUser, getCurrentUserId } from '../store/userStore'
import { formatUtc } from '../utils/dates'

// What each permission controls in the backend (see backend/app/services/permission_gate.py).
const PERMISSION_HELP = {
  timetable: 'Your available hours per day - needed to simulate your capacity.',
  goals: 'Goal titles - help TwinMate recognise which task your question is about.',
  tasks: 'Tasks, estimates and deadlines - needed to simulate plans.',
  history: 'Collecting and analyzing your study / work activity (observations and outcomes).',
  preferences: 'Your preferred working time - decides the order of your simulated day.',
  behavior: 'Your learned Twin traits (productivity, estimation, delays) in simulations.',
}
const FORGET_OPTIONS = [
  { key: 'tasks', label: 'Tasks & Deadlines', countKey: 'tasks' },
  { key: 'history', label: 'Study / Work History (what-if runs and feedback)', countKey: 'scenario_runs' },
  { key: 'observations', label: 'Behavioral Observations (also removes the traits calculated from them)', countKey: 'observations' },
  { key: 'patterns', label: 'Inferred Patterns (Twin traits only - observations are kept)', countKey: 'traits_with_values' },
  { key: 'preferences', label: 'Preferences (available hours, working time)', countKey: 'preferences' },
  { key: 'goals', label: 'Goals', countKey: 'goals' },
]
const INVENTORY_LABELS = {
  goals: 'Goals', tasks: 'Tasks', preferences: 'Preference records', observations: 'Behavioral observations',
  traits_with_values: 'Twin traits with a value', scenario_runs: 'What-if runs', feedback: 'Feedback entries',
  twin_updates: 'Twin updates',
}

function Notice({ kind = 'success', children }) {
  const style = kind === 'error' ? 'border-red-200 bg-red-50 text-red-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'
  return <p role={kind === 'error' ? 'alert' : 'status'} className={`rounded-lg border px-3 py-2 text-sm ${style}`}>{children}</p>
}

export default function PrivacyPage() {
  const navigate = useNavigate()
  const userId = getCurrentUserId()

  const [user, setUser] = useState(null)
  const [privacy, setPrivacy] = useState(null)
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [busy, setBusy] = useState('') // which action is running
  const [notice, setNotice] = useState({ kind: '', text: '' })
  const [dataUsed, setDataUsed] = useState(null)
  const [forgetSelection, setForgetSelection] = useState([])
  const [confirmOpen, setConfirmOpen] = useState(false)

  const refreshLogs = useCallback(async () => {
    try {
      setLogs(await getAccessLogs(userId, 15))
    } catch {
      /* the log list is optional - the rest of the page still works */
    }
  }, [userId])

  const load = useCallback(async () => {
    setLoadError('')
    try {
      const [u, p] = await Promise.all([getUser(userId), getPrivacy(userId)])
      setUser(u)
      setPrivacy(p)
      await refreshLogs()
    } catch (err) {
      if (err.response?.status === 404) {
        clearCurrentUser()
        setLoadError('We could not find your Twin in the database (it may have been reset). Please create it again.')
      } else {
        setLoadError(getErrorMessage(err, 'Unable to load your privacy settings.'))
      }
    } finally {
      setLoading(false)
    }
  }, [userId, refreshLogs])

  useEffect(() => {
    if (!userId) {
      navigate('/', { replace: true })
      return
    }
    load()
  }, [userId, load, navigate])

  // Runs one action with its own loading state, then refreshes the activity list.
  async function act(name, fn, errorText) {
    setBusy(name)
    setNotice({ kind: '', text: '' })
    try {
      await fn()
      await refreshLogs()
    } catch (err) {
      setNotice({ kind: 'error', text: getErrorMessage(err, errorText) })
    } finally {
      setBusy('')
    }
  }

  const togglePermission = (key, value) =>
    act(`perm-${key}`, async () => {
      const p = await updatePermissions(userId, { [key]: value })
      setPrivacy(p)
      setNotice({ kind: 'success', text: p.message })
    }, 'Unable to update privacy settings.')

  const toggleLearning = () =>
    act('learning', async () => {
      const p = await setLearningPaused(userId, !privacy.learning_paused)
      setPrivacy(p)
      setNotice({ kind: 'success', text: p.message })
    }, 'Unable to update privacy settings.')

  const showDataUsed = () =>
    act('data-used', async () => setDataUsed(await getDataUsed(userId)), 'Unable to load the data used.')

  const downloadExport = () =>
    act('export', async () => {
      const data = await exportTwin(userId)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `twinmate-export-${data.generated_at.slice(0, 10)}.json`
      document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
      setNotice({ kind: 'success', text: 'Your Twin was exported as a JSON file.' })
    }, 'Export failed. Please try again.')

  const confirmForget = () =>
    act('forget', async () => {
      const result = await forgetData(userId, forgetSelection)
      setConfirmOpen(false)
      setForgetSelection([])
      setDataUsed(null)
      setPrivacy(await getPrivacy(userId))
      setNotice({ kind: 'success', text: [result.message, ...result.notes].join(' ') })
    }, 'The data could not be forgotten. Nothing was removed.')

  if (!userId) return null
  if (loading) return <div className="flex min-h-screen items-center justify-center text-slate-500">Loading privacy settings...</div>

  if (!privacy || !user) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <main className="mx-auto max-w-md px-6 py-16 text-center">
          <Notice kind="error">{loadError}</Notice>
          <div className="mt-4">
            {getCurrentUserId() ? <Button onClick={() => { setLoading(true); load() }}>Try again</Button>
              : <Button onClick={() => navigate('/onboarding')}>Create My Twin</Button>}
          </div>
        </main>
      </div>
    )
  }

  const inv = privacy.inventory
  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar userName={user.name} onStartOver={() => { clearCurrentUser(); navigate('/') }} />
      <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Privacy &amp; Data Control</h1>
          <p className="mt-1 text-slate-500">Your data belongs to you. Control what TwinMate can use and learn from.</p>
        </div>

        {notice.text && <Notice kind={notice.kind}>{notice.text}</Notice>}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Data permissions">
            <ul className="divide-y divide-slate-100">
              {Object.entries(privacy.permission_labels).map(([key, label]) => (
                <li key={key} className="flex items-start justify-between gap-4 py-3">
                  <div>
                    <p className="font-medium text-slate-800">{label}</p>
                    <p className="text-xs text-slate-500">{PERMISSION_HELP[key]}</p>
                  </div>
                  <Toggle label={label} checked={privacy.permissions[key]} disabled={Boolean(busy)}
                    onChange={(value) => togglePermission(key, value)} />
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-slate-400">Changes are saved on the server immediately and apply to the next simulation.</p>
          </Card>

          <div className="space-y-6">
            <Card title="Learning">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="font-medium text-slate-800">Learning from my activity</p>
                  <p className={`mt-1 text-sm ${privacy.learning_paused ? 'font-medium text-amber-700' : 'text-slate-500'}`}>
                    {privacy.learning_message}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-semibold ${
                  privacy.learning_paused ? 'border-amber-200 bg-amber-50 text-amber-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                }`}>
                  {privacy.learning_paused ? 'PAUSED' : 'ON'}
                </span>
              </div>
              <div className="mt-4">
                <Button variant={privacy.learning_paused ? 'primary' : 'secondary'} onClick={toggleLearning}
                  loading={busy === 'learning'} disabled={Boolean(busy)}>
                  {privacy.learning_paused ? 'Resume Learning' : 'Pause Learning'}
                </Button>
              </div>
            </Card>

            <Card title="Your data">
              <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                {Object.entries(INVENTORY_LABELS).map(([key, label]) => (
                  <li key={key} className="flex justify-between gap-2 text-slate-600">
                    <span>{label}</span><strong className="text-slate-900">{inv[key]}</strong>
                  </li>
                ))}
              </ul>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button variant="secondary" onClick={showDataUsed} loading={busy === 'data-used'} disabled={Boolean(busy)}>View Data Used</Button>
                <Button onClick={downloadExport} loading={busy === 'export'} disabled={Boolean(busy)}>
                  {busy === 'export' ? 'Exporting Twin...' : 'Export My Twin'}
                </Button>
              </div>
            </Card>
          </div>
        </div>

        {dataUsed && (
          <Card title="Data used for your latest recommendation">
            {dataUsed.categories.length === 0 ? (
              <p className="text-sm text-slate-500">{dataUsed.message}</p>
            ) : (
              <>
                <p className="mb-3 text-sm text-slate-600">
                  "{dataUsed.question}" <span className="text-slate-400">· {formatUtc(dataUsed.created_at)}</span>
                  <span className="block text-xs text-slate-400">Shows the permissions as they were when this recommendation was generated.</span>
                </p>
                <DataUsedPanel categories={dataUsed.categories} />
              </>
            )}
          </Card>
        )}

        <Card title="Forget data">
          <p className="mb-3 text-sm text-slate-600">Choose what you want TwinMate to forget. This permanently deletes it.</p>
          <div className="space-y-2">
            {FORGET_OPTIONS.map((o) => (
              <label key={o.key} className="flex items-center gap-3 text-sm text-slate-700">
                <input type="checkbox" className="h-4 w-4 rounded border-slate-300 accent-indigo-600"
                  checked={forgetSelection.includes(o.key)} disabled={Boolean(busy)}
                  onChange={(e) => setForgetSelection(e.target.checked ? [...forgetSelection, o.key] : forgetSelection.filter((k) => k !== o.key))} />
                <span>{o.label} <span className="text-slate-400">({inv[o.countKey]} stored)</span></span>
              </label>
            ))}
          </div>
          <div className="mt-4">
            <Button variant="danger" disabled={forgetSelection.length === 0 || Boolean(busy)} onClick={() => setConfirmOpen(true)}>
              Forget Selected Data
            </Button>
          </div>
        </Card>

        <Card title="Recent data activity">
          {logs.length === 0 ? (
            <p className="text-sm text-slate-400">No data activity has been recorded yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100 text-sm">
              {logs.map((l) => (
                <li key={l.id} className="flex items-center justify-between gap-3 py-2">
                  <span className="text-slate-800">{l.text}{l.detail && <span className="text-slate-400"> - {l.detail}</span>}</span>
                  <span className="shrink-0 text-xs text-slate-400">{formatUtc(l.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </main>

      <ConfirmDialog
        open={confirmOpen}
        title="Are you sure?"
        confirmLabel="Confirm"
        busy={busy === 'forget'}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={confirmForget}
      >
        <p>This will permanently remove:</p>
        <ul className="mt-2 list-disc pl-5">
          {FORGET_OPTIONS.filter((o) => forgetSelection.includes(o.key)).map((o) => <li key={o.key}>{o.label}</li>)}
        </ul>
        <p className="mt-2">Removed data cannot be restored and will not be used for future Twin updates.</p>
      </ConfirmDialog>
    </div>
  )
}
