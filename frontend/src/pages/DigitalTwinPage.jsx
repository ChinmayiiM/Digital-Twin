import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AddObservationForm from '../components/AddObservationForm'
import Button from '../components/Button'
import Card from '../components/Card'
import EvidenceLog from '../components/EvidenceLog'
import Navbar from '../components/Navbar'
import ProductivityCard from '../components/ProductivityCard'
import TwinTraitCard from '../components/TwinTraitCard'
import TwinUpdatesCard from '../components/TwinUpdatesCard'
import {
  analyzeTwin,
  clearDemoData,
  getErrorMessage,
  getObservations,
  getPrivacy,
  getTwin,
  getTwinUpdates,
  getUser,
  seedDemoData,
} from '../services/api'
import { clearCurrentUser, getCurrentUserId } from '../store/userStore'
import { formatUtc } from '../utils/dates'

export default function DigitalTwinPage() {
  const navigate = useNavigate()
  const userId = getCurrentUserId()

  const [user, setUser] = useState(null)
  const [twin, setTwin] = useState(null)
  const [observations, setObservations] = useState([])
  const [updates, setUpdates] = useState([]) // Phase 5: learning from feedback
  const [privacy, setPrivacy] = useState(null) // Phase 6: permissions + learning status
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [busy, setBusy] = useState('') // '', 'analyze', 'seed', 'clear'

  const load = useCallback(async () => {
    setLoadError('')
    try {
      const [u, t, o] = await Promise.all([getUser(userId), getTwin(userId), getObservations(userId, 15)])
      setUser(u)
      setTwin(t)
      setObservations(o)
      // Optional (Phase 5): if this fails, the rest of the Twin page still works.
      try {
        setUpdates(await getTwinUpdates(userId, 3))
      } catch {
        setUpdates([])
      }
      try {
        setPrivacy(await getPrivacy(userId))
      } catch {
        setPrivacy(null)
      }
    } catch (err) {
      if (err.response?.status === 404) {
        clearCurrentUser()
        setLoadError('We could not find your Twin in the database (it may have been reset). Please create it again.')
      } else {
        setLoadError(getErrorMessage(err, 'Unable to load your Digital Twin.'))
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

  // Runs one action, then refreshes everything from the backend.
  async function run(name, fn, fallback) {
    setBusy(name)
    setActionError('')
    setNotice('')
    try {
      await fn()
      await load()
    } catch (err) {
      setActionError(getErrorMessage(err, fallback))
    } finally {
      setBusy('')
    }
  }

  const updateTwin = () =>
    run('analyze', async () => {
      await analyzeTwin(userId)
      setNotice('Twin updated from the stored observations.')
    }, 'Unable to update the Twin. Please try again.')

  const loadDemo = () =>
    run('seed', async () => {
      await seedDemoData(userId) // 1) stores synthetic observations (labelled "demo")
      await analyzeTwin(userId) // 2) the Pattern Analyzer turns them into traits
      setNotice('Synthetic demo observations were stored and analyzed.')
    }, 'Unable to load demo data.')

  const removeDemo = () =>
    run('clear', async () => {
      await clearDemoData(userId)
      await analyzeTwin(userId)
      setNotice('Synthetic demo observations removed and the Twin rebuilt.')
    }, 'Unable to remove demo data.')

  if (!userId) return null
  if (loading) return <div className="flex min-h-screen items-center justify-center text-slate-500">Loading your Digital Twin...</div>

  if (!twin || !user) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <main className="mx-auto max-w-md px-6 py-16 text-center">
          <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{loadError}</p>
          <div className="mt-4">
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

  const learningBlocked = Boolean(privacy && (privacy.learning_paused || !privacy.permissions.history))
  const byName = Object.fromEntries(twin.traits.map((t) => [t.trait_name, t]))
  const productivity = ['productivity_morning', 'productivity_afternoon', 'productivity_evening'].map((n) => byName[n])
  const otherTraits = ['task_estimation', 'focus_capacity', 'task_ordering', 'procrastination'].map((n) => byName[n])

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar
        userName={user.name}
        onStartOver={() => { clearCurrentUser(); navigate('/') }}
      />
      <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">Digital Twin</p>
          <h1 className="text-3xl font-bold text-slate-900">{user.name}'s Personal Twin</h1>
          <p className="mt-1 text-slate-500">Your Twin learns from your actual behavior over time.</p>
        </div>

        {privacy?.learning_paused && (
          <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <strong>Learning is paused.</strong> Your existing Twin is still available, but new activity will not update
            your behavioral traits until learning is resumed on the Privacy &amp; Data page.
          </p>
        )}
        {privacy && !privacy.permissions.history && (
          <p role="status" className="rounded-lg border border-slate-200 bg-slate-100 px-4 py-3 text-sm text-slate-700">
            The <strong>Study / Work History</strong> permission is off, so new observations are not stored or analyzed.
          </p>
        )}
        {privacy && !privacy.permissions.behavior && (
          <p role="status" className="rounded-lg border border-slate-200 bg-slate-100 px-4 py-3 text-sm text-slate-700">
            The <strong>Behavioral Patterns</strong> permission is off: these traits are shown to you, but they are not
            used in simulations or recommendations.
          </p>
        )}

        {/* status + actions */}
        <Card>
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div className="space-y-1 text-sm text-slate-600">
              <p>
                <strong className="text-slate-900">{twin.total_observations}</strong> observation
                {twin.total_observations === 1 ? '' : 's'} stored
                {twin.analyzed && <> · last analyzed {formatUtc(twin.last_analyzed)}</>}
              </p>
              {twin.demo_observations > 0 && (
                <p className="text-amber-700">
                  Includes {twin.demo_observations} synthetic demo observation{twin.demo_observations === 1 ? '' : 's'} (not real behavior).
                </p>
              )}
              {twin.observations_pending_analysis > 0 && (
                <p className="font-medium text-indigo-700">
                  {twin.observations_pending_analysis} new observation{twin.observations_pending_analysis === 1 ? '' : 's'} not analyzed yet.
                </p>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button onClick={updateTwin} loading={busy === 'analyze'} disabled={Boolean(busy) || learningBlocked}
                title={learningBlocked ? 'Learning is not allowed right now (see Privacy & Data)' : undefined}>
                {busy === 'analyze' ? 'Updating Twin...' : 'Update Twin'}
              </Button>
              {twin.demo_observations === 0 ? (
                <Button variant="secondary" onClick={loadDemo} loading={busy === 'seed'} disabled={Boolean(busy) || learningBlocked}>Load synthetic demo data</Button>
              ) : (
                <Button variant="secondary" onClick={removeDemo} loading={busy === 'clear'} disabled={Boolean(busy) || learningBlocked}
                  title={learningBlocked ? 'Resume learning first, or use Forget Data on the Privacy & Data page' : undefined}>
                  Remove demo data
                </Button>
              )}
            </div>
          </div>
          {actionError && <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>}
          {notice && <p role="status" className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{notice}</p>}
        </Card>

        {!twin.analyzed ? (
          <Card>
            <p className="font-semibold text-slate-900">Your Twin does not have enough behavioral evidence yet.</p>
            <p className="mt-1 text-sm text-slate-500">
              Add observations below (or load the synthetic demo data), then click <strong>Update Twin</strong>.
              Until there is enough evidence, TwinMate will say "Not enough evidence yet" instead of guessing.
            </p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <ProductivityCard traits={productivity} statedPreference={twin.stated_preference} />
            {otherTraits.map((t) => (
              <TwinTraitCard key={t.trait_name} trait={t} />
            ))}
          </div>
        )}

        <TwinUpdatesCard updates={updates} />

        <p className="text-xs text-slate-400">
          How to read this: values are learned with new = old + {twin.config.alpha} × (observed − old). Confidence =
          observations ÷ {twin.config.full_confidence_at} (capped at 100%) and shows how much evidence exists, not
          statistical certainty. At least {twin.config.minimum_evidence} observations are needed before a value is shown.
        </p>

        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <AddObservationForm userId={userId} onAdded={load} />
          <EvidenceLog observations={observations} total={twin.total_observations} />
        </div>
      </main>
    </div>
  )
}
