import { useNavigate } from 'react-router-dom'
import BackendStatus from '../components/BackendStatus'
import Button from '../components/Button'
import { getCurrentUserId } from '../store/userStore'

export default function LandingPage() {
  const navigate = useNavigate()
  const hasTwin = Boolean(getCurrentUserId())

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-slate-50 via-white to-indigo-50 p-6">
      <div className="w-full max-w-xl text-center">
        <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-indigo-600 text-3xl font-bold text-white shadow-lg shadow-indigo-200">
          T
        </div>
        <h1 className="text-5xl font-bold tracking-tight text-slate-900">TwinMate AI</h1>
        <p className="mt-3 text-xl text-slate-600">Your Digital Twin for Smarter Decisions</p>
        <p className="mx-auto mt-5 max-w-md text-slate-500">
          TwinMate learns your goals, schedule, preferences and behavioral patterns to help simulate decisions and
          provide personalized recommendations.
        </p>

        <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Button onClick={() => navigate('/onboarding')} className="px-6 py-3 text-base">
            Create My Twin
          </Button>
          {hasTwin && (
            <Button variant="secondary" onClick={() => navigate('/dashboard')} className="px-6 py-3 text-base">
              Open My Dashboard
            </Button>
          )}
        </div>

        <div className="mt-10">
          <BackendStatus />
        </div>
        <p className="mt-4 text-xs text-slate-400">GATEWAYS 2026 · Round 2 · HumanTwin AI</p>
      </div>
    </div>
  )
}
