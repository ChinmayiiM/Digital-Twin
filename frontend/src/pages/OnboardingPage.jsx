import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Button from '../components/Button'
import Card from '../components/Card'
import GoalCard from '../components/GoalCard'
import Input, { Select, Textarea } from '../components/Input'
import Navbar from '../components/Navbar'
import TaskCard from '../components/TaskCard'
import {
  createGoal,
  createTask,
  createUser,
  getErrorMessage,
  savePreferences,
} from '../services/api'
import { setCurrentUserId } from '../store/userStore'
import { inputValueDaysFromNow, toApiDateTime } from '../utils/dates'

const STEPS = ['Basics', 'Goals', 'Tasks', 'Availability', 'Review']

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
]
const WORK_TIMES = ['Morning', 'Afternoon', 'Evening', 'Flexible']

const emptyGoal = { title: '', description: '', priority: 'medium' }
const emptyTask = { title: '', description: '', goalLocalId: '', estimated_hours: '', deadline: '', priority: 'medium' }

export default function OnboardingPage() {
  const navigate = useNavigate()

  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [goals, setGoals] = useState([])
  const [goalDraft, setGoalDraft] = useState(emptyGoal)
  const [tasks, setTasks] = useState([])
  const [taskDraft, setTaskDraft] = useState(emptyTask)
  const [hours, setHours] = useState('')
  const [workTime, setWorkTime] = useState('')

  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [locked, setLocked] = useState(false) // true once the user row exists in the database

  const nextLocalId = useRef(1)
  // Remembers what is already saved, so pressing "Try again" after a failure never creates duplicates.
  const progress = useRef({ userId: null, goalIds: {}, tasksSaved: 0, prefsSaved: false })

  const goalTitleOf = (localId) => goals.find((g) => g.localId === Number(localId))?.title

  // ---------- goals ----------
  function addGoal() {
    if (!goalDraft.title.trim()) return setError('Please enter a goal title.')
    setGoals([...goals, { ...goalDraft, title: goalDraft.title.trim(), localId: nextLocalId.current++ }])
    setGoalDraft(emptyGoal)
    setError('')
  }

  function removeGoal(localId) {
    setGoals(goals.filter((g) => g.localId !== localId))
    // tasks that pointed at this goal become "no goal"
    setTasks(tasks.map((t) => (t.goalLocalId === localId ? { ...t, goalLocalId: '' } : t)))
  }

  // ---------- tasks ----------
  function addTask() {
    if (!taskDraft.title.trim()) return setError('Please enter a task title.')
    const h = Number(taskDraft.estimated_hours)
    if (!taskDraft.estimated_hours || Number.isNaN(h) || h <= 0) return setError('Estimated hours must be greater than 0.')
    if (!taskDraft.deadline) return setError('Please choose a deadline for the task.')
    setTasks([
      ...tasks,
      {
        ...taskDraft,
        title: taskDraft.title.trim(),
        estimated_hours: h,
        goalLocalId: taskDraft.goalLocalId === '' ? '' : Number(taskDraft.goalLocalId),
        localId: nextLocalId.current++,
      },
    ])
    setTaskDraft(emptyTask)
    setError('')
  }

  // ---------- navigation ----------
  function next() {
    setError('')
    if (step === 1 && !name.trim()) return setError('Please enter your name.')
    if (step === 2) {
      if (goalDraft.title.trim()) return setError('You have a goal that is not added yet. Click "+ Add Goal" first.')
      if (goals.length === 0) return setError('Please add at least one goal.')
    }
    if (step === 3) {
      if (taskDraft.title.trim()) return setError('You have a task that is not added yet. Click "+ Add Task" first.')
      if (tasks.length === 0) return setError('Please add at least one task.')
    }
    if (step === 4) {
      const h = Number(hours)
      if (!hours || Number.isNaN(h) || h <= 0 || h > 24) return setError('Available hours per day must be between 0 and 24.')
      if (!workTime) return setError('Please select when you prefer to work.')
    }
    setStep(step + 1)
  }

  function back() {
    setError('')
    setStep(step - 1)
  }

  function fillDemo() {
    setName('Alex')
    setGoals([
      { localId: 1, title: 'Prepare for ML Exam', description: 'Complete exam preparation', priority: 'high' },
      { localId: 2, title: 'Complete ML Assignment', description: 'Finish the semester assignment', priority: 'high' },
    ])
    setTasks([
      { localId: 3, title: 'ML Assignment', description: 'Complete assignment', goalLocalId: 2, estimated_hours: 5, deadline: inputValueDaysFromNow(1), priority: 'high' },
      { localId: 4, title: 'ML Exam Preparation', description: 'Revise all units', goalLocalId: 1, estimated_hours: 8, deadline: inputValueDaysFromNow(3), priority: 'high' },
    ])
    nextLocalId.current = 5
    setHours('6')
    setWorkTime('Morning')
    setError('')
  }

  // ---------- save: user -> goals -> tasks -> preferences -> dashboard ----------
  async function handleSave() {
    setSaving(true)
    setError('')
    const p = progress.current
    let stage = 'user'
    try {
      if (!p.userId) {
        const user = await createUser({ name: name.trim() })
        p.userId = user.id
        setLocked(true)
      }

      stage = 'goal'
      for (const g of goals) {
        if (p.goalIds[g.localId]) continue
        const saved = await createGoal({
          user_id: p.userId,
          title: g.title,
          description: g.description.trim() || null,
          priority: g.priority,
        })
        p.goalIds[g.localId] = saved.id
      }

      stage = 'task'
      for (let i = p.tasksSaved; i < tasks.length; i++) {
        const t = tasks[i]
        await createTask({
          user_id: p.userId,
          goal_id: t.goalLocalId === '' ? null : p.goalIds[t.goalLocalId] ?? null,
          title: t.title,
          description: t.description.trim() || null,
          estimated_hours: t.estimated_hours,
          deadline: toApiDateTime(t.deadline),
          priority: t.priority,
          status: 'pending',
        })
        p.tasksSaved = i + 1
      }

      stage = 'preferences'
      if (!p.prefsSaved) {
        await savePreferences(p.userId, {
          available_hours_per_day: Number(hours),
          preferred_working_time: workTime,
        })
        p.prefsSaved = true
      }

      setCurrentUserId(p.userId)
      navigate('/dashboard')
    } catch (err) {
      const fallback = {
        user: 'Unable to create your profile. Please try again.',
        goal: 'Unable to save goal. Please try again.',
        task: 'Unable to save task. Please try again.',
        preferences: 'Unable to save preferences. Please try again.',
      }[stage]
      setError(getErrorMessage(err, fallback))
    } finally {
      setSaving(false)
    }
  }

  const goalOptions = [
    { value: '', label: 'No specific goal' },
    ...goals.map((g) => ({ value: g.localId, label: g.title })),
  ]

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50">
      <Navbar />
      <main className="mx-auto max-w-2xl px-6 py-8">
        {/* progress indicator */}
        <ol className="mb-6 flex items-center justify-between text-xs font-medium">
          {STEPS.map((label, i) => {
            const n = i + 1
            const active = n === step
            const done = n < step
            return (
              <li key={label} className="flex flex-1 flex-col items-center gap-1">
                <span
                  className={`flex h-7 w-7 items-center justify-center rounded-full border text-xs ${
                    active ? 'border-indigo-600 bg-indigo-600 text-white' : done ? 'border-indigo-600 bg-indigo-50 text-indigo-600' : 'border-slate-300 bg-white text-slate-400'
                  }`}
                >
                  {done ? '✓' : n}
                </span>
                <span className={active ? 'text-indigo-600' : 'text-slate-400'}>{label}</span>
              </li>
            )
          })}
        </ol>

        <Card>
          {/* STEP 1 */}
          {step === 1 && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Let's meet you</h1>
                <p className="text-sm text-slate-500">This is the start of your Digital Twin.</p>
              </div>
              <Input label="Your name" placeholder="e.g. Alex" value={name} onChange={(e) => setName(e.target.value)} maxLength={100} autoFocus />
              <button type="button" onClick={fillDemo} className="text-xs font-medium text-indigo-600 hover:underline">
                Fill with demo data (Alex)
              </button>
            </div>
          )}

          {/* STEP 2 */}
          {step === 2 && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Your goals</h1>
                <p className="text-sm text-slate-500">What are you trying to achieve? Add one or more.</p>
              </div>
              <div className="space-y-2">
                {goals.map((g) => (
                  <GoalCard key={g.localId} goal={g} onRemove={() => removeGoal(g.localId)} />
                ))}
              </div>
              <div className="space-y-3 rounded-xl border border-dashed border-slate-300 p-4">
                <Input label="Goal title" placeholder="e.g. Prepare for ML Exam" value={goalDraft.title} onChange={(e) => setGoalDraft({ ...goalDraft, title: e.target.value })} maxLength={200} />
                <Textarea label="Description (optional)" value={goalDraft.description} onChange={(e) => setGoalDraft({ ...goalDraft, description: e.target.value })} />
                <Select label="Priority" options={PRIORITY_OPTIONS} value={goalDraft.priority} onChange={(e) => setGoalDraft({ ...goalDraft, priority: e.target.value })} />
                <Button variant="secondary" onClick={addGoal}>+ Add Goal</Button>
              </div>
            </div>
          )}

          {/* STEP 3 */}
          {step === 3 && (
            <div className="space-y-4">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Your tasks</h1>
                <p className="text-sm text-slate-500">What has to get done, and by when?</p>
              </div>
              <div className="space-y-2">
                {tasks.map((t) => (
                  <TaskCard
                    key={t.localId}
                    task={{ ...t, status: 'pending' }}
                    goalTitle={t.goalLocalId === '' ? null : goalTitleOf(t.goalLocalId)}
                    onRemove={() => setTasks(tasks.filter((x) => x.localId !== t.localId))}
                  />
                ))}
              </div>
              <div className="space-y-3 rounded-xl border border-dashed border-slate-300 p-4">
                <Input label="Task title" placeholder="e.g. ML Assignment" value={taskDraft.title} onChange={(e) => setTaskDraft({ ...taskDraft, title: e.target.value })} maxLength={200} />
                <Textarea label="Description (optional)" value={taskDraft.description} onChange={(e) => setTaskDraft({ ...taskDraft, description: e.target.value })} />
                <Select label="Goal" options={goalOptions} value={taskDraft.goalLocalId} onChange={(e) => setTaskDraft({ ...taskDraft, goalLocalId: e.target.value })} />
                <div className="grid grid-cols-2 gap-3">
                  <Input label="Estimated hours" type="number" min="0.5" step="0.5" placeholder="5" value={taskDraft.estimated_hours} onChange={(e) => setTaskDraft({ ...taskDraft, estimated_hours: e.target.value })} />
                  <Select label="Priority" options={PRIORITY_OPTIONS} value={taskDraft.priority} onChange={(e) => setTaskDraft({ ...taskDraft, priority: e.target.value })} />
                </div>
                <Input label="Deadline" type="datetime-local" value={taskDraft.deadline} onChange={(e) => setTaskDraft({ ...taskDraft, deadline: e.target.value })} />
                <Button variant="secondary" onClick={addTask}>+ Add Task</Button>
              </div>
            </div>
          )}

          {/* STEP 4 */}
          {step === 4 && (
            <div className="space-y-5">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Availability &amp; preference</h1>
                <p className="text-sm text-slate-500">Tell us how you like to work.</p>
              </div>
              <Input label="How many hours can you work/study per day?" type="number" min="0.5" max="24" step="0.5" placeholder="6" value={hours} onChange={(e) => setHours(e.target.value)} />
              <div>
                <p className="mb-2 text-sm font-medium text-slate-700">When do you usually prefer to work?</p>
                <div className="grid grid-cols-2 gap-3">
                  {WORK_TIMES.map((w) => (
                    <button
                      key={w}
                      type="button"
                      onClick={() => setWorkTime(w)}
                      className={`rounded-lg border px-4 py-3 text-sm font-medium transition ${
                        workTime === w ? 'border-indigo-600 bg-indigo-50 text-indigo-700' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      {w}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* STEP 5 */}
          {step === 5 && (
            <div className="space-y-5">
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Review &amp; create</h1>
                <p className="text-sm text-slate-500">Everything below will be saved to your TwinMate database.</p>
              </div>
              <dl className="divide-y divide-slate-100 text-sm">
                <div className="flex justify-between py-2"><dt className="text-slate-500">Name</dt><dd className="font-medium">{name.trim()}</dd></div>
                <div className="flex justify-between py-2"><dt className="text-slate-500">Goals</dt><dd className="font-medium">{goals.length}</dd></div>
                <div className="flex justify-between py-2"><dt className="text-slate-500">Tasks</dt><dd className="font-medium">{tasks.length}</dd></div>
                <div className="flex justify-between py-2"><dt className="text-slate-500">Available hours / day</dt><dd className="font-medium">{hours}</dd></div>
                <div className="flex justify-between py-2"><dt className="text-slate-500">Preferred time</dt><dd className="font-medium">{workTime}</dd></div>
              </dl>
              <Button onClick={handleSave} loading={saving} className="w-full py-3 text-base">
                {saving ? 'Saving...' : progress.current.userId ? 'Try again' : 'Create My Twin'}
              </Button>
            </div>
          )}

          {error && (
            <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          {step < 5 && (
            <div className="mt-6 flex justify-between">
              <Button variant="ghost" onClick={back} disabled={step === 1}>Back</Button>
              <Button onClick={next}>Next</Button>
            </div>
          )}
          {step === 5 && (
            <div className="mt-4">
              <Button variant="ghost" onClick={back} disabled={saving || locked}>Back</Button>
            </div>
          )}
        </Card>
      </main>
    </div>
  )
}
