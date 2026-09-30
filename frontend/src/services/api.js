import axios from 'axios'
import { getCurrentUserId } from '../store/userStore'

// One place for the backend URL. Override with VITE_API_URL in frontend/.env if needed.
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

const api = axios.create({ baseURL: API_BASE_URL, timeout: 8000 })

// Phase 6: tell the backend which Twin is asking, so it can refuse access to other users' data.
// (There is no login in this MVP - see README "Limitations".)
api.interceptors.request.use((config) => {
  const id = getCurrentUserId()
  if (id) config.headers['X-User-Id'] = id
  return config
})

const data = (res) => res.data

// ---- Phase 1 ----
export const getHealth = () => api.get('/api/health').then(data)

// ---- Users ----
export const createUser = (payload) => api.post('/api/users', payload).then(data)
export const getUser = (userId) => api.get(`/api/users/${userId}`).then(data)

// ---- Goals ----
export const createGoal = (payload) => api.post('/api/goals', payload).then(data)
export const getGoals = (userId) => api.get(`/api/goals/user/${userId}`).then(data)
export const deleteGoal = (goalId) => api.delete(`/api/goals/${goalId}`)

// ---- Tasks ----
export const createTask = (payload) => api.post('/api/tasks', payload).then(data)
export const getTasks = (userId) => api.get(`/api/tasks/user/${userId}`).then(data)
export const updateTask = (taskId, payload) => api.put(`/api/tasks/${taskId}`, payload).then(data)
export const deleteTask = (taskId) => api.delete(`/api/tasks/${taskId}`)

// ---- Preferences ----
export const getPreferences = (userId) => api.get(`/api/preferences/${userId}`).then(data)
export const savePreferences = (userId, payload) =>
  api.put(`/api/preferences/${userId}`, payload).then(data)

// ---- Dashboard ----
export const getDashboard = (userId) => api.get(`/api/dashboard/${userId}`).then(data)

// ---- Digital Twin (Phase 3) ----
export const getTwin = (userId) => api.get(`/api/twin/${userId}/traits`).then(data)
export const analyzeTwin = (userId) => api.post(`/api/twin/${userId}/analyze`).then(data)
export const getObservations = (userId, limit = 15) =>
  api.get(`/api/observations/user/${userId}`, { params: { limit } }).then(data)
export const createObservation = (payload) => api.post('/api/observations', payload).then(data)
export const seedDemoData = (userId) => api.post(`/api/demo/seed/${userId}`).then(data)
export const clearDemoData = (userId) => api.delete(`/api/demo/seed/${userId}`).then(data)

// ---- What-If Simulator (Phase 4) ----
// The full simulation (and an optional LLM call on the server) can take longer than the default 8 s.
export const analyzeWhatIf = (userId, question) =>
  api.post('/api/simulator/analyze', { user_id: Number(userId), question }).then(data)
export const runWhatIf = (userId, question) =>
  api.post('/api/simulator/run', { user_id: Number(userId), question }, { timeout: 60000 }).then(data)

// ---- Feedback & learning loop (Phase 5) ----
export const submitFeedback = (payload) => api.post('/api/feedback', payload).then(data)
export const rerunScenario = (userId, scenarioId) =>
  api.post(`/api/simulator/rerun/${scenarioId}`, { user_id: Number(userId) }, { timeout: 60000 }).then(data)
export const getTwinUpdates = (userId, limit = 5) =>
  api.get(`/api/twin/${userId}/updates`, { params: { limit } }).then(data)

// ---- Privacy & Data Control (Phase 6) ----
export const getPrivacy = (userId) => api.get(`/api/privacy/${userId}`).then(data)
export const updatePermissions = (userId, changes) => api.put(`/api/privacy/${userId}/permissions`, changes).then(data)
export const setLearningPaused = (userId, paused) => api.put(`/api/privacy/${userId}/learning`, { paused }).then(data)
export const forgetData = (userId, categories) =>
  api.post(`/api/privacy/${userId}/forget`, { categories, confirm: true }).then(data)
export const getDataUsed = (userId, scenarioId) =>
  api.get(`/api/privacy/${userId}/data-used`, { params: scenarioId ? { scenario_id: scenarioId } : {} }).then(data)
export const exportTwin = (userId) => api.get(`/api/privacy/${userId}/export`, { timeout: 20000 }).then(data)
export const getAccessLogs = (userId, limit = 15) =>
  api.get(`/api/privacy/${userId}/access-logs`, { params: { limit } }).then(data)

// ---- Errors ----
export const CONNECTION_ERROR =
  'Unable to connect to TwinMate server. Please make sure the backend is running.'

/** Turns an Axios error into a message that can be shown to the user. */
export function getErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
  if (!err.response) return CONNECTION_ERROR
  const detail = err.response.data?.detail
  return typeof detail === 'string' && detail ? `${fallback} (${detail})` : fallback
}

export default api
