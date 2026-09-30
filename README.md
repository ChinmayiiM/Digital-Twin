# TwinMate AI - Personal Digital Decision Twin

**GATEWAYS 2026 · Round 2** · Problem statement: **HumanTwin AI - The Intelligent Digital Twin of a Person**

## 1. The problem
Planning tools and chatbots give generic advice ("do the urgent task first"). They do not know how *you* work:
that your tasks usually take longer than you estimate, that you are sharper in the morning, or that you tend to
finish late. So their advice does not fit you, and they never learn whether it helped.

## 2. The solution
TwinMate builds a **Digital Twin** of the person - a structured, evidence-based model of their behavior - and uses
it to **simulate "what-if" decisions** before they make them. After the decision, the person reports what really
happened, the Twin **learns**, shows **exactly what changed**, and the same decision can be **re-simulated** with
the updated Twin. The person controls what the Twin may use and learn.

## 3. Key features
- **Onboarding & dashboard** - goals, tasks, deadlines, estimates, priorities, available hours, preferred working time
- **Digital Twin** - 7 learned traits (morning / afternoon / evening productivity, task estimation, focus capacity,
  task ordering, procrastination), each with value, confidence and evidence; "Not enough evidence yet" instead of guessing
- **What-If Simulator** - natural-language question → 3 plans → NumPy Monte Carlo (1,000 runs per plan) →
  comparison → explicit recommendation score → explanation, uncertainty range and the Twin data used
- **Learning loop** - feedback with actual outcomes → behavioral observations → Twin update → Twin Diff (before → after,
  with the formula) → re-run the same question with the updated Twin
- **Privacy & data control** - 6 permissions enforced by the backend, pause/resume learning, "view data used",
  forget data by category (with confirmation), JSON export, access log

## 4. Architecture
```text
User Data → Permission Gate → Twin Memory → Pattern Analysis → Scenario Simulation → Scenario Comparison
   → Recommendation → User Feedback → Twin Update → Twin Diff → Re-run → Privacy / Data Controls
```
React (Vite, Tailwind, Recharts) → Axios → FastAPI routers → services (plain Python + NumPy) → SQLAlchemy → SQLite.
An LLM is **optional** and never calculates anything.

## 5. Agentic workflow
| Step | What happens | Code |
|---|---|---|
| **Reason** | Understand the question (rules; optional LLM → validated JSON) | `services/scenario_parser.py` |
| **Plan** | Build Plan A / B / C from the user's real tasks | `services/scenario_planner.py` |
| **Take action** | Simulate every plan (typical day + Monte Carlo) | `services/scenario_simulator.py` |
| **Decide** | Compare and score the plans | `services/scenario_comparator.py`, `services/recommender.py` |
| **Learn** | Turn feedback into behavioral observations | `services/feedback_learning.py` |
| **Adapt** | Update the Twin, save the Twin Diff | `services/pattern_analyzer.py` |
| **Repeat** | Re-run the same question with the updated Twin | `POST /api/simulator/rerun/{id}` |
| **Control** | Permission gate, pause, forget, export, logs | `services/permission_gate.py`, `services/privacy_service.py` |

Every step shows in the UI with its real duration and result - nothing is animated or faked.

## 6. The Digital Twin
The Twin is built only from **observations** (what the person actually did), never from what they said they prefer.
- Learning formula: `new = old + 0.2 × (observed − old)` (recent behavior counts more)
- Confidence: `min(1, evidence / 10)` - how much evidence exists, not statistical certainty
- Fewer than 3 observations → no value is shown ("Not enough evidence yet")
- Stated preferences (e.g. "I prefer mornings") are kept separate from observed behavior

## 7. What-If Simulator
- Required hours = estimate × the Twin's estimation ratio (e.g. 5 h × 1.42 = 7.1 h)
- Each working hour produces `productivity factor × fatigue factor` hours of progress; productivity is applied
  relative to the person's own average (the estimation ratio already reflects normal speed - no double counting)
- The day follows the preferred working time (first 4 h in that period); fatigue after 4 h; each task switch
  costs 5% of the day; procrastination can cost 1 h per day
- Monte Carlo: 1,000 runs per plan, fixed seed 42, the same random draws for every plan
- Recommendation score = 0.4 × progress + 0.4 × on-time chance − 0.3 × worst deadline risk − 0.2 × overload
  + 0.03 habit bonus; top two within 0.03 → **"No clear preference"**
- Clarification for vague questions, over-capacity warning for impossible ones, "limited evidence" warning
- All constants: `backend/app/services/simulation_config.py`

## 8. Feedback learning loop
- Only **measured** outcomes teach the Twin: the actual hours of a *completed* task (→ estimation) and whether it
  met the deadline (→ procrastination). Ratings, preferences, changed schedules and general statements are stored
  and explained, but never change a trait.
- The feedback is saved as the newest observation and the Phase 3 analyzer re-reads the history, which is exactly the
  formula above. Feedback, observations, traits and the before/after snapshot are saved in **one transaction**.
- Re-run recalculates everything (nothing is reused) and shows previous → current values.

## 9. Privacy & data controls
| Permission | When OFF, the backend… |
|---|---|
| Timetable & Available Hours | has no capacity → the simulator stops and says which permission to enable |
| Goals | does not use goal titles to recognise tasks in a question |
| Tasks & Deadlines | has no tasks → the simulator stops and says why |
| Study / Work History | stores no new observations and does not analyze them (feedback is kept without observations) |
| Preferences | ignores the preferred working time (the day order follows observed productivity) |
| Behavioral Patterns | uses **no** learned trait in simulations - neutral values, marked "Permission off" |

- **Pause learning:** the existing Twin stays and is still used; new feedback is stored but creates no
  observations; "Update Twin" is refused. **Resume** makes learning possible again.
- **Forget** (confirmation required, one transaction): tasks, goals, preferences, behavioral observations (also
  removes the traits calculated from them), inferred patterns (traits only - observations are kept and the Twin can
  be rebuilt), study/work history (what-if runs, feedback, Twin updates).
- **View data used:** every recommendation stores which categories were permitted and exactly what was used.
- **Export:** a JSON file with the user's own data (no internal ids, no settings or secrets).
- **Access log:** Twin viewed, scenario run, recommendation generated, feedback submitted, Twin updated, permission
  changed, learning paused/resumed, data forgotten, data used viewed, Twin exported (short, non-sensitive text only).

## 10. Technology stack
Backend: Python 3.11, FastAPI, SQLAlchemy 2, SQLite, Pydantic 2, NumPy, python-dotenv, Uvicorn.
Frontend: React 19, Vite, Tailwind CSS 4, Axios, Recharts, React Router. No LangChain, no agent framework, no cloud services.

## 11. Project structure
```text
backend/
  app/main.py              FastAPI app, CORS, table creation, health check
  app/database.py          engine, session, Base
  app/models/              User, Goal, Task, Preference, BehaviorObservation, TwinTrait,
                           ScenarioRun, Feedback, TwinSnapshot, Permission, AccessLog
  app/schemas/             Pydantic request/response models (validation)
  app/routers/             users, goals, tasks, preferences, dashboard, observations, twin, demo,
                           simulator, feedback, privacy
  app/services/            pattern_analyzer, demo_data, twin_context, scenario_parser, scenario_planner,
                           scenario_simulator, scenario_comparator, recommender, llm_client, llm_explainer,
                           whatif_pipeline, scenario_store, feedback_learning, permission_gate, access_log,
                           privacy_service, simulation_config
  seed_demo.py             creates the synthetic demo user "Alex"
  test_phase4.py / test_phase5.py / test_phase6.py
frontend/src/
  pages/                   Landing, Onboarding, Dashboard, DigitalTwin, WhatIf, Privacy
  components/              shared UI (Card, Button, Input, Toggle, ConfirmDialog, ...) and simulator/ components
  services/api.js          every API call in one place
  store/userStore.js       remembers the current user id
```

## 12. Setup
### Backend (terminal 1)
```bash
cd backend
python -m venv venv
venv\Scripts\activate           
pip install -r requirements.txt
uvicorn app.main:app --reload
```
API: http://127.0.0.1:8000 · Swagger: http://127.0.0.1:8000/docs

### Frontend (terminal 2)
```bash
cd frontend
npm install
npm run dev
```
App: http://localhost:5173

Tables are created automatically on startup; existing data is never touched.

## 13. Environment variables (`backend/.env`, template in `backend/.env.example`)
| Variable | Meaning |
|---|---|
| `DATABASE_URL` | default `sqlite:///./twinmate.db` |
| `LLM_PROVIDER` | `none` (default), `anthropic`, or `openai` (any OpenAI-compatible API) |
| `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_TIMEOUT_SECONDS` | only needed if an LLM is used |

Keys stay on the backend and never reach the React app, the export or the logs. `backend/.env` is gitignored.
Frontend (optional): `VITE_API_URL` if the API is not on http://127.0.0.1:8000.

## 14. Backend commands
```bash
cd backend
uvicorn app.main:app --reload       # run the API
python seed_demo.py                 # optional: synthetic demo user "Alex"
python test_phase4.py               # What-If simulator (41 checks)
python test_phase5.py               # learning loop (47 checks)
python test_phase6.py               # privacy + full regression (69 checks)
```
The tests use their own throwaway databases.

## 15. Frontend commands
```bash
cd frontend
npm run dev        # development server
npm run build      # production build (checks that everything compiles)
```

## 16. Main API endpoints
| Area | Endpoints |
|---|---|
| Health | `GET /api/health` |
| Profile | `/api/users`, `/api/goals`, `/api/tasks`, `/api/preferences/{id}`, `GET /api/dashboard/{id}` |
| Twin | `GET /api/twin/{id}/traits`, `POST /api/twin/{id}/analyze`, `GET /api/twin/{id}/updates`, `/api/observations`, `/api/demo/seed/{id}` |
| Simulator | `POST /api/simulator/analyze`, `POST /api/simulator/run`, `POST /api/simulator/rerun/{scenario_id}` |
| Feedback | `POST /api/feedback` |
| Privacy | `GET /api/privacy/{id}`, `PUT …/permissions`, `PUT …/learning`, `POST …/forget`, `GET …/data-used`, `GET …/export`, `GET …/access-logs` |

Full request/response schemas: Swagger at `/docs`.

## 17. Demo flow (about 5 minutes)
1. Onboarding → **Fill with demo data (Alex)** → Save (or `python seed_demo.py`).
2. **Dashboard:** 6 h/day, ML Assignment (5 h, due tomorrow), ML Exam Preparation (8 h, due in 3 days), goals.
3. **Digital Twin** → **Load synthetic demo data**: morning 79 %, tasks take 42 % longer, evidence and confidence.
4. **What-If Simulator:** "What if I spend tomorrow only preparing for my exam and postpone my assignment?"
   → 3 plans, comparison, recommendation (**Plan C - assignment first**: the Twin knows the assignment really needs
   ≈7.1 h and it is due tomorrow), reasons, uncertainty range, Twin data used, data used.
5. **Feedback:** Partially helpful · "The task took longer than expected" · ML Assignment · 6.5 h · completed · on time.
6. **Twin Diff:** estimation +42 % → +40 % (it took longer than the estimate, but less than the Twin expected),
   evidence 4 → 5, with the formula. (Enter 8 h instead to show it moving up: +42 % → +46 %.)
7. **Re-run This Scenario:** assignment needs 6.99 h instead of 7.11 h; Plan C's on-time chance rises.
8. **Privacy & Data:** switch **Behavioral Patterns** off → run the question again → every trait shows
   "Permission off" and estimates are used as-is. **Pause learning** → feedback no longer changes the Twin.
   **View data used**, **Export My Twin** (JSON download), **Recent data activity**.

## 18. Limitations
- **No login.** The browser remembers the user id; privacy endpoints require a matching `X-User-Id` header and task/goal
  changes are checked against the owner, which stops casual cross-user access but is **not** real authentication.
  A real deployment needs accounts and sessions/JWT.
- The demo behavior data is **synthetic** (clearly labelled). Real use needs weeks of observations.
- The simulation is an explainable estimate, not a scientific prediction; its constants are reasonable defaults.
- The question parser is rule-based (optional LLM) and handles schedule-trade-off questions between tasks.
- Partial task progress is not tracked yet (every task starts at 0 % in a simulation).
- SQLite and a single process: fine for a demo, not for many concurrent users.

## 19. Future improvements
- Authentication and per-user encryption at rest
- Automatic observations from calendars / task tools (with the same permission gate)
- Partial progress tracking and recurring tasks
- Per-task-type estimation traits (assignments vs. exam preparation)
- Tuning the simulator constants from real outcome data
- Scheduled reminders to collect outcome feedback
