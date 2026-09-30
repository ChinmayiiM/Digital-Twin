"""Phase 4 checks - run from the backend/ folder:   python test_phase4.py

Uses a separate throwaway database (test_phase4.db), so your real twinmate.db is never touched.
Needs httpx for FastAPI's TestClient (listed in requirements.txt).
Every check prints PASS/FAIL; the script exits with code 1 if anything fails.
"""
import os
import sys
from datetime import datetime, timedelta

TEST_DB = "test_phase4.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB}"
os.environ["LLM_PROVIDER"] = "none"  # Test 6: the simulator must work without any LLM

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import llm_client  # noqa: E402

client = TestClient(app)
failures = []


def check(name, condition, info=""):
    print(("PASS " if condition else "FAIL ") + name + (f"  -> {info}" if info and not condition else ""))
    if not condition:
        failures.append(name)


def make_alex(with_twin=True, hours=6):
    uid = client.post("/api/users", json={"name": "Alex"}).json()["id"]
    exam = client.post("/api/goals", json={"user_id": uid, "title": "Prepare for ML Exam", "priority": "high"}).json()["id"]
    assign = client.post("/api/goals", json={"user_id": uid, "title": "Complete ML Assignment", "priority": "high"}).json()["id"]
    six_pm = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    client.post("/api/tasks", json={"user_id": uid, "goal_id": assign, "title": "ML Assignment", "estimated_hours": 5,
                                    "deadline": (six_pm + timedelta(days=1)).isoformat(), "priority": "high"})
    client.post("/api/tasks", json={"user_id": uid, "goal_id": exam, "title": "ML Exam Preparation", "estimated_hours": 8,
                                    "deadline": (six_pm + timedelta(days=3)).isoformat(), "priority": "high"})
    client.put(f"/api/preferences/{uid}", json={"available_hours_per_day": hours, "preferred_working_time": "Morning"})
    if with_twin:
        client.post(f"/api/demo/seed/{uid}")
        client.post(f"/api/twin/{uid}/analyze")
    return uid


def run(uid, question):
    res = client.post("/api/simulator/run", json={"user_id": uid, "question": question})
    assert res.status_code == 200, res.text
    return res.json()


alex = make_alex()

# ---- Test 1: basic scenario
r1 = run(alex, "What if I spend tomorrow only preparing for my exam and postpone my assignment?")
check("T1 status ok", r1["status"] == "ok", r1.get("message"))
check("T1 focus = exam, postpone = assignment",
      r1["intent"]["focus_task_title"] == "ML Exam Preparation" and r1["intent"]["deferred_task_titles"] == ["ML Assignment"])
check("T1 three plans", len(r1["plans"]) == 3)
check("T1 six workflow steps", [w["step"] for w in r1["workflow"]] ==
      ["understand", "plan", "simulate", "compare", "decide", "explain"])
check("T1 comparison + recommendation + explanation",
      bool(r1["comparison"]["rows"]) and r1["recommendation"]["headline"] and r1["explanation"]["text"])
check("T1 Twin data comes from the Twin (morning 79%, +42%)",
      any(i["label"] == "Morning productivity" and i["value"] == "79%" for i in r1["twin_data_used"]) and
      any("42% longer" in i["value"] for i in r1["twin_data_used"]))
check("T1 adjusted hours = 5 x Twin ratio", abs(r1["plans"][0]["tasks"][0]["adjusted_required_hours"] - 7.11) < 0.05)
low, high = r1["confidence"]["outcome_low"], r1["confidence"]["outcome_high"]
check("T1 range contains expected", low <= r1["confidence"]["expected_outcome"] <= high)

# ---- Test 2: different wording -> same structure
for q in ("Suppose I focus only on exam preparation tomorrow and delay my ML assignment.",
          "Suppose I postpone my assignment and study for the exam instead.",
          "What if I focus only on my exam tomorrow?"):
    r = run(alex, q)
    check(f"T2 '{q[:40]}...' same intent", r["status"] == "ok" and
          r["intent"]["focus_task_title"] == "ML Exam Preparation" and r["intent"]["deferred_task_titles"] == ["ML Assignment"],
          r.get("message") or r.get("intent"))
    check("T2 same numbers as T1 (deterministic seed)", r["status"] != "ok" or
          r["recommendation"]["scores"] == r1["recommendation"]["scores"])
r = run(alex, "What if I finish my assignment first and postpone the exam?")
check("T2 reversed question is understood the other way round",
      r["status"] == "ok" and r["intent"]["focus_task_title"] == "ML Assignment")

# ---- Test 3: ambiguous
r = run(alex, "What if I study more tomorrow?")
check("T3 clarification required", r["status"] == "clarification_needed" and not r["plans"], r["status"])
check("T3 asks which task", "Which task or goal" in (r["message"] or ""))

# ---- Test 4: over capacity
r = run(alex, "What if I complete all 20 hours of work tomorrow?")
check("T4 over capacity", r["status"] == "over_capacity" and r["capacity"]["requested_hours"] == 20
      and r["capacity"]["available_hours"] == 6, r.get("capacity"))
check("T4 message", "requires approximately 20 hours" in r["message"] and "6 hours/day" in r["message"])
r = run(alex, "What if I finish all my work tomorrow?")
check("T4b 'all my work' uses Twin-adjusted hours", r["status"] == "over_capacity" and r["capacity"]["requested_hours"] > 13)

# ---- Test 5: insufficient Twin data
fresh = make_alex(with_twin=False)
r = run(fresh, "What if I spend tomorrow only preparing for my exam and postpone my assignment?")
check("T5 still simulates", r["status"] == "ok" and len(r["plans"]) == 3)
check("T5 limited evidence shown", r["confidence"]["limited_evidence"] and
      "limited evidence" in r["confidence"]["message"] and r["confidence"]["label"] == "Low")
check("T5 no invented Twin values", all(i["source"] in ("profile", "fallback") for i in r["twin_data_used"]))
check("T5 estimates used as-is", r["plans"][0]["tasks"][0]["adjusted_required_hours"] == 5.0)

# ---- Test 6: LLM unavailable / broken / lying
check("T6 fallback explanation without LLM", r1["explanation"]["source"] == "simulation_results" and
      r1["explanation"]["label"] == "Explanation generated from simulation results.")
os.environ.update(LLM_PROVIDER="anthropic", LLM_API_KEY="test-key", LLM_MODEL="test-model")
original = llm_client.complete
try:
    llm_client.complete = lambda *a, **k: None  # timeout / network error
    r = run(alex, "What if I spend tomorrow only preparing for my exam and postpone my assignment?")
    check("T6 LLM down -> same result, fallback text", r["status"] == "ok" and
          r["explanation"]["source"] == "simulation_results" and r["recommendation"] == r1["recommendation"])

    llm_client.complete = lambda *a, **k: "Sure! here is {not json"  # malformed output
    r = run(alex, "What if I spend tomorrow only preparing for my exam and postpone my assignment?")
    check("T6 malformed LLM JSON -> rules parser", r["status"] == "ok" and r["understood_by"] == "rules")

    llm_client.complete = lambda *a, **k: '{"intent": "reschedule_work", "focus_task_id": 99999, "deferred_task_ids": []}'
    r = run(alex, "What if I spend tomorrow only preparing for my exam and postpone my assignment?")
    check("T6 LLM with unknown task id is rejected", r["understood_by"] == "rules")

    def fake_llm(system, user, max_tokens=500):
        if "convert" in system:  # intent extraction: valid JSON with the real ids
            import json
            tasks = json.loads(user)["tasks"]
            exam = next(t for t in tasks if "Exam" in t["title"])
            assign = next(t for t in tasks if "Assignment" in t["title"])
            return f'```json\n{{"intent": "reschedule_work", "focus_task_id": {exam["id"]}, "deferred_task_ids": [{assign["id"]}], "time_horizon": "tomorrow"}}\n```'
        return "Plan C fits best. It gives a 97% chance of success."  # invents a number
    llm_client.complete = fake_llm
    r = run(alex, "I'd rather cram for the test and leave the homework")
    check("T6 valid LLM JSON is used for understanding", r["status"] == "ok" and r["understood_by"] == "llm")
    check("T6 LLM explanation with invented number is rejected", r["explanation"]["source"] == "simulation_results")

    llm_client.complete = lambda system, user, max_tokens=500: (
        None if "convert" in system else "Plan C is the safer choice because your assignment is due first.")
    r = run(alex, "What if I spend tomorrow only preparing for my exam and postpone my assignment?")
    check("T6 honest LLM explanation is accepted and labelled", r["explanation"]["source"] == "llm"
          and "LLM" in r["explanation"]["label"])
finally:
    llm_client.complete = original
    os.environ.update(LLM_PROVIDER="none", LLM_API_KEY="", LLM_MODEL="")

# ---- other edge cases
r = run(alex, "What if I spend today only on my exam and postpone the assignment?")
check("Edge 'today' horizon", r["status"] == "ok" and r["intent"]["time_horizon"] == "today")
no_pref = client.post("/api/users", json={"name": "NoPrefs"}).json()["id"]
check("Edge no preferences -> not_enough_data", run(no_pref, "What if I study for my exam?")["status"] == "not_enough_data")
check("Edge unknown user -> 404", client.post("/api/simulator/run", json={"user_id": 999999, "question": "hello there"}).status_code == 404)
check("Edge empty question -> 422", client.post("/api/simulator/run", json={"user_id": alex, "question": "  "}).status_code == 422)
a = client.post("/api/simulator/analyze", json={"user_id": alex, "question": "What if I postpone my assignment?"}).json()
check("Edge /analyze: postpone only -> focus implied", a["status"] == "ok" and a["intent"]["focus_task_title"] == "ML Exam Preparation")

# ---- no clear preference: two small tasks with far deadlines -> every plan finishes both
easy = client.post("/api/users", json={"name": "Easy"}).json()["id"]
later = (datetime.now() + timedelta(days=5)).replace(hour=18, minute=0, second=0, microsecond=0)
for title in ("Read chapter", "Write summary"):
    client.post("/api/tasks", json={"user_id": easy, "title": title, "estimated_hours": 1,
                                    "deadline": later.isoformat(), "priority": "medium"})
client.put(f"/api/preferences/{easy}", json={"available_hours_per_day": 6, "preferred_working_time": "Flexible"})
r = run(easy, "What if I only read the chapter tomorrow and postpone the summary?")
check("Edge similar outcomes -> no clear preference", r["status"] == "ok" and
      r["recommendation"]["no_clear_preference"] and r["recommendation"]["recommended_plan_id"] is None,
      r.get("recommendation") or r.get("message"))

# ---- Test 7: Phase 1-3 still work
check("T7 /api/health", client.get("/api/health").json()["status"] == "ok")
check("T7 dashboard", client.get(f"/api/dashboard/{alex}").json()["tasks_count"] == 2)
check("T7 twin traits", len(client.get(f"/api/twin/{alex}/traits").json()["traits"]) == 7)
check("T7 observations", client.get(f"/api/observations/user/{alex}").status_code == 200)

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED: {failures}"))
client.close()
from app.database import engine  # noqa: E402

engine.dispose()
os.remove(TEST_DB)
sys.exit(1 if failures else 0)
