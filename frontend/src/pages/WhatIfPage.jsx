import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Card from '../components/Card'
import Navbar from '../components/Navbar'
import DataUsedPanel from '../components/DataUsedPanel'
import ComparisonTable from '../components/simulator/ComparisonTable'
import FeedbackForm from '../components/simulator/FeedbackForm'
import LearningEffect from '../components/simulator/LearningEffect'
import PlanCard from '../components/simulator/PlanCard'
import RecommendationCard from '../components/simulator/RecommendationCard'
import TwinDataUsed from '../components/simulator/TwinDataUsed'
import TwinDiff from '../components/simulator/TwinDiff'
import UncertaintyCard from '../components/simulator/UncertaintyCard'
import WorkflowSteps from '../components/simulator/WorkflowSteps'
import { getDashboard, getErrorMessage, rerunScenario, runWhatIf } from '../services/api'
import { clearCurrentUser, getCurrentUserId } from '../store/userStore'
import { taskColour } from '../utils/format'

// Styling for answers that are not a full simulation (the backend returns these with HTTP 200).
const STATUS_BOX = {
  clarification_needed: { title: 'Clarification needed', style: 'border-amber-200 bg-amber-50 text-amber-800' },
  over_capacity: { title: 'This plan is over capacity', style: 'border-red-200 bg-red-50 text-red-800' },
  not_enough_data: { title: 'Not enough data to simulate yet', style: 'border-slate-200 bg-slate-50 text-slate-700' },
}

/** Example questions built from the user's own open tasks (earliest deadline first). */
function exampleQuestions(tasks) {
  const open = tasks.filter((t) => t.status !== 'completed' && t.deadline)
  const list = []
  if (open.length >= 2) {
    list.push(`What if I spend tomorrow only on ${open[1].title} and postpone ${open[0].title}?`)
    list.push(`What if I finish ${open[0].title} first and postpone ${open[1].title}?`)
  }
  list.push('What if I study more tomorrow?')
  list.push('What if I complete 20 hours of work tomorrow?')
  return list
}

export default function WhatIfPage() {
  const navigate = useNavigate()
  const userId = getCurrentUserId()

  const [dashboard, setDashboard] = useState(null)
  const [loadError, setLoadError] = useState('')
  const [question, setQuestion] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [feedback, setFeedback] = useState(null) // Phase 5: response of POST /api/feedback (Twin Diff)

  const load = useCallback(async () => {
    setLoadError('')
    try {
      setDashboard(await getDashboard(userId))
    } catch (err) {
      if (err.response?.status === 404) {
        clearCurrentUser()
        setLoadError('We could not find your Twin in the database (it may have been reset). Please create it again.')
      } else {
        setLoadError(getErrorMessage(err, 'Unable to load your data.'))
      }
    }
  }, [userId])

  useEffect(() => {
    if (!userId) {
      navigate('/', { replace: true })
      return
    }
    load()
  }, [userId, load, navigate])

  async function simulate(text = question) {
    const q = text.trim()
    if (q.length < 3) return setError('Please describe the decision you are thinking about.')
    setQuestion(q)
    setError('')
    setResult(null)
    setFeedback(null)
    setRunning(true)
    try {
      setResult(await runWhatIf(userId, q))
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to run the simulation. Please try again.'))
    } finally {
      setRunning(false)
    }
  }

  // Phase 5: the SAME question again - the backend recalculates everything with the current Twin.
  async function rerun() {
    const scenarioId = result.scenario_id
    setError('')
    setResult(null)
    setFeedback(null)
    setRunning(true)
    window.scrollTo({ top: 0, behavior: 'smooth' })
    try {
      setResult(await rerunScenario(userId, scenarioId))
    } catch (err) {
      setError(getErrorMessage(err, 'Unable to re-run the scenario.'))
    } finally {
      setRunning(false)
    }
  }

  if (!userId) return null

  if (!dashboard) {
    return (
      <div className="min-h-screen bg-slate-50">
        <Navbar />
        <main className="mx-auto max-w-md px-6 py-16 text-center">
          {loadError ? (
            <>
              <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{loadError}</p>
              <div className="mt-4">
                {getCurrentUserId() ? <Button onClick={load}>Try again</Button> : <Button onClick={() => navigate('/onboarding')}>Create My Twin</Button>}
              </div>
            </>
          ) : (
            <p className="text-slate-500">Loading...</p>
          )}
        </main>
      </div>
    )
  }

  const ok = result?.status === 'ok'
  const statusBox = result && !ok ? STATUS_BOX[result.status] : null
  const colourIndex = ok ? Object.fromEntries(result.plans[0].tasks.map((t, i) => [t.task_id, i])) : {}
  const colourOf = (taskId) => taskColour(colourIndex[taskId] ?? 0)
  const recommendedId = ok ? result.recommendation.recommended_plan_id : null
  const planForConfidence = ok ? result.plans.find((p) => p.id === recommendedId) || result.plans.find((p) => p.is_user_proposal) : null

  return (
    <div className="min-h-screen bg-slate-50">
      <Navbar userName={dashboard.user.name} onStartOver={() => { clearCurrentUser(); navigate('/') }} />
      <main className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">What-If Decision Simulator</h1>
          <p className="mt-1 text-slate-500">
            TwinMate simulates your options with your own Twin data, compares them, and recommends a plan.
          </p>
        </div>

        {/* ---------------- question ---------------- */}
        <Card>
          <form onSubmit={(e) => { e.preventDefault(); simulate() }}>
            <label htmlFor="whatif-question" className="block text-lg font-semibold text-slate-900">
              What are you thinking about?
            </label>
            <textarea
              id="whatif-question"
              rows={3}
              maxLength={500}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What if I spend tomorrow only preparing for my exam and postpone my assignment?"
              className="mt-3 w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-base text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              {exampleQuestions(dashboard.tasks).map((q) => (
                <button
                  key={q}
                  type="button"
                  disabled={running}
                  onClick={() => simulate(q)}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-50"
                >
                  {q}
                </button>
              ))}
            </div>
            {error && <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
            <div className="mt-4 flex justify-center">
              <Button type="submit" loading={running} className="px-6 py-3 text-base">Simulate Decision</Button>
            </div>
          </form>
        </Card>

        {(running || result) && <WorkflowSteps running={running} workflow={result?.workflow} />}

        {/* ---------------- clarification / over capacity / no data ---------------- */}
        {statusBox && (
          <div role="status" className={`rounded-2xl border px-5 py-4 ${statusBox.style}`}>
            <p className="font-semibold">{statusBox.title}</p>
            <p className="mt-1 text-sm">{result.message}</p>
            {result.suggestions.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-medium">Try asking:</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {result.suggestions.map((s) => (
                    <button key={s} type="button" onClick={() => simulate(s)}
                      className="rounded-full border border-current/20 bg-white px-3 py-1 text-xs hover:underline">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ---------------- full result ---------------- */}
        {ok && (
          <>
            {result.learning_effect && <LearningEffect effect={result.learning_effect} />}

            <Card title="Your question">
              <p className="text-lg text-slate-900">"{result.question}"</p>
              <p className="mt-2 text-sm text-slate-500">
                Understood as: focus on <strong>{result.intent.focus_task_title}</strong>, postpone{' '}
                <strong>{result.intent.deferred_task_titles.join(', ')}</strong>
                {result.intent.deferred_is_implicit && ' (implied - it has the nearest other deadline)'}, starting{' '}
                {result.intent.time_horizon}.
              </p>
            </Card>

            <section>
              <h2 className="mb-3 text-xl font-bold text-slate-900">Possible plans</h2>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                {result.plans.map((p) => (
                  <PlanCard key={p.id} plan={p} colourOf={colourOf} recommended={p.id === recommendedId} />
                ))}
              </div>
            </section>

            <ComparisonTable comparison={result.comparison} plans={result.plans} />
            <RecommendationCard recommendation={result.recommendation} explanation={result.explanation} />

            <TwinDataUsed items={result.twin_data_used} />
            <UncertaintyCard
              confidence={result.confidence}
              settings={result.settings}
              planLabel={`Plan ${planForConfidence.id}`}
            />

            <Card title="Data used for this recommendation">
              <DataUsedPanel categories={result.data_used} />
              <p className="mt-3 text-xs text-slate-400">
                Only permitted data is used. Change what TwinMate may use on the Privacy &amp; Data page.
              </p>
            </Card>

            <Card title="Assumptions behind this simulation">
              <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
                {result.assumptions.map((a) => <li key={a}>{a}</li>)}
              </ul>
              <p className="mt-3 text-xs text-slate-400">
                {result.settings.simulations_per_plan.toLocaleString()} simulations per plan · random seed {result.settings.random_seed} ·
                all numbers calculated in Python/NumPy on the server.
              </p>
            </Card>

            {result.scenario_id ? (
              feedback ? (
                <TwinDiff feedback={feedback} onRerun={rerun} rerunning={running} />
              ) : (
                <FeedbackForm userId={userId} result={result} onSubmitted={setFeedback} />
              )
            ) : (
              <p className="text-center text-sm text-slate-400">This run could not be saved, so feedback is not available for it.</p>
            )}
          </>
        )}
      </main>
    </div>
  )
}
