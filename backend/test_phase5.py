"""Phase 5 checks - run from the backend/ folder:   python test_phase5.py

Tests the learning loop: feedback -> observation -> Twin update -> Twin Diff -> re-run.
Uses its own throwaway database (test_phase5.db); your real twinmate.db is never touched.
"""
import os
import sys
from datetime import datetime, timedelta

TEST_DB = "test_phase5.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB}"
os.environ["LLM_PROVIDER"] = "none"  # Test 7: everything must work without an LLM

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
failures = []
QUESTION = "What if I spend tomorrow only preparing for my exam and postpone my assignment?"


def check(name, condition, info=""):
    print(("PASS " if condition else "FAIL ") + name + (f"  -> {info}" if info and not condition else ""))
    if not condition:
        failures.append(name)


def make_alex(with_twin=True):
    uid = client.post("/api/users", json={"name": "Alex"}).json()["id"]
    six_pm = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    assignment = client.post("/api/tasks", json={"user_id": uid, "title": "ML Assignment", "estimated_hours": 5,
                                                 "deadline": (six_pm + timedelta(days=1)).isoformat(),
                                                 "priority": "high"}).json()["id"]
    exam = client.post("/api/tasks", json={"user_id": uid, "title": "ML Exam Preparation", "estimated_hours": 8,
                                           "deadline": (six_pm + timedelta(days=3)).isoformat(),
                                           "priority": "high"}).json()["id"]
    client.put(f"/api/preferences/{uid}", json={"available_hours_per_day": 6, "preferred_working_time": "Morning"})
    if with_twin:
        client.post(f"/api/demo/seed/{uid}")
        client.post(f"/api/twin/{uid}/analyze")
    return uid, assignment, exam


def simulate(uid):
    res = client.post("/api/simulator/run", json={"user_id": uid, "question": QUESTION}).json()
    assert res["status"] == "ok", res
    return res


def feedback(uid, sid, **extra):
    body = {"user_id": uid, "scenario_id": sid, "rating": "partially_helpful", **extra}
    return client.post("/api/feedback", json=body)


def trait(uid, name):
    return next(t for t in client.get(f"/api/twin/{uid}/traits").json()["traits"] if t["trait_name"] == name)


# ---------------------------------------------------------------- setup
alex, assignment, exam = make_alex()
run1 = simulate(alex)
check("Run is stored with a scenario_id", isinstance(run1["scenario_id"], int))

# ---- TEST 1: helpful feedback without outcome -> saved, Twin unchanged
before_traits = client.get(f"/api/twin/{alex}/traits").json()["traits"]
res = feedback(alex, run1["scenario_id"], rating="helpful", reasons=["matched_situation"])
check("T1 helpful feedback saved (201)", res.status_code == 201, res.text)
check("T1 no Twin change", res.json()["updated"] is False and res.json()["changes"] == []
      and client.get(f"/api/twin/{alex}/traits").json()["traits"] == before_traits)

# ---- TEST 2: task took longer -> observation, estimation trait changes by the formula, evidence +1
old = trait(alex, "task_estimation")
res = feedback(alex, run1["scenario_id"], reasons=["task_took_longer"], task_id=assignment, actual_hours=6.5,
               completed=True, deadline_met=True, notes="The assignment took longer than expected.")
body = res.json()
check("T2 feedback accepted", res.status_code == 201, res.text)
change = next((c for c in body.get("changes", []) if c["trait_name"] == "task_estimation"), None)
new = trait(alex, "task_estimation")
expected = old["trait_value"] + 0.2 * (6.5 / 5 - old["trait_value"])
check("T2 observation created (actual 6.5 / est 5)", any(o["observation_type"] == "task_estimation" and
      o["observed_value"] == 6.5 for o in body["interpretation"]["observations"]))
check("T2 new = old + 0.2 x (observed - old)", abs(new["trait_value"] - expected) < 0.001,
      f"{new['trait_value']} vs {expected}")
check("T2 evidence +1", new["evidence_count"] == old["evidence_count"] + 1)
check("T2 Twin Diff uses real before/after", change is not None and change["before_value"] == old["trait_value"]
      and change["after_value"] == new["trait_value"] and change["evidence_before"] == old["evidence_count"])
check("T2 diff has reason + formula", "6.5 h vs 5 h" in change["reason"] and change["formula"] is not None)
check("T2 on-time -> delay observation too", any(c["trait_name"] == "procrastination" for c in body["changes"]))
check("T2 snapshot saved and listed", body["snapshot_id"] is not None and
      client.get(f"/api/twin/{alex}/updates").json()[0]["snapshot_id"] == body["snapshot_id"])

# ---- TEST 3: feedback without behavioral evidence -> saved, no change
run_x = simulate(alex)
before_traits = client.get(f"/api/twin/{alex}/traits").json()["traits"]
res = feedback(alex, run_x["scenario_id"], rating="not_helpful", reasons=["schedule_changed", "prefer_other_option"],
               notes="I prefer studying at night and my plans changed at the last minute.")
check("T3 saved", res.status_code == 201, res.text)
check("T3 no significant change + message", res.json()["updated"] is False
      and "No significant trait changes" in res.json()["message"])
check("T3 preference does not change behavior traits",
      client.get(f"/api/twin/{alex}/traits").json()["traits"] == before_traits
      and any("Preferences are stored" in n for n in res.json()["interpretation"]["notes"]))

# ---- TEST 4 + 5: re-run uses the updated Twin and recalculates
rerun = client.post(f"/api/simulator/rerun/{run1['scenario_id']}", json={"user_id": alex}).json()
check("T4 re-run: same question, new scenario", rerun["status"] == "ok" and rerun["question"] == QUESTION
      and rerun["scenario_id"] != run1["scenario_id"] and rerun["rerun_of"] == run1["scenario_id"])
used = next(i for i in rerun["twin_data_used"] if i["label"] == "Task estimation tendency")
check("T4 updated Twin values used", used["evidence_count"] == new["evidence_count"]
      and used["value"] == new["display_value"])
old_adj = run1["plans"][0]["tasks"][0]["adjusted_required_hours"]
new_adj = rerun["plans"][0]["tasks"][0]["adjusted_required_hours"]
check("T5 result recalculated (adjusted hours follow the new ratio)", new_adj != old_adj
      and abs(new_adj - 5 * new["trait_value"]) < 0.02, f"{old_adj} -> {new_adj}")
check("T5 learning effect reported", rerun["learning_effect"]["twin_changes"] and
      "updated Twin was used" in rerun["learning_effect"]["message"])
same = client.post(f"/api/simulator/rerun/{rerun['scenario_id']}", json={"user_id": alex}).json()
check("T5 unchanged Twin -> identical numbers (deterministic)", same["learning_effect"]["twin_changes"] == []
      and same["plans"] == rerun["plans"])

# ---- TEST 6: invalid hours
for bad, word in ((-5, "greater than 0"), (0, "greater than 0"), (1000, "at most 100")):
    res = feedback(alex, rerun["scenario_id"], task_id=assignment, actual_hours=bad, completed=True)
    check(f"T6 actual_hours={bad} rejected", res.status_code == 422 and word in res.json()["detail"], res.text)
res = feedback(alex, rerun["scenario_id"], task_id=assignment, actual_hours=90, completed=True)
check("T6 unrealistic vs estimate (90 h for 5 h) rejected", res.status_code == 422 and "unrealistic" in res.text)
res = feedback(alex, rerun["scenario_id"], task_id=assignment, actual_hours="abc", completed=True)
check("T6 non-number rejected", res.status_code == 422)

# ---- TEST 7: no LLM configured -> learning still works (already the case in T2)
check("T7 works without LLM", os.environ["LLM_PROVIDER"] == "none" and body["updated"] is True)

# ---- edge cases
check("E1 no scenario_id -> 422", client.post("/api/feedback", json={"user_id": alex, "rating": "helpful"}).status_code == 422)
check("E6 feedback without reason is fine", feedback(alex, simulate(alex)["scenario_id"], rating="helpful").status_code == 201)
r = feedback(alex, simulate(alex)["scenario_id"], actual_hours=6)
check("E7 outcome without task -> clear message", r.status_code == 422 and "Choose which task" in r.json()["detail"])
r = feedback(alex, simulate(alex)["scenario_id"], task_id=assignment, actual_hours=8, completed=False, deadline_met=False)
check("E8 unfinished task -> stored, no estimation update", r.status_code == 201 and
      not any(c["trait_name"] == "task_estimation" for c in r.json()["changes"]))
r = feedback(alex, run1["scenario_id"], task_id=assignment, actual_hours=6, completed=True)
check("E13 duplicate feedback for same task -> 409", r.status_code == 409 and "already recorded" in r.json()["detail"])
check("E14 unknown scenario -> 404", feedback(alex, 999999).status_code == 404)
other, _, _ = make_alex()
check("E14 other user's scenario -> 404", feedback(other, run1["scenario_id"]).status_code == 404)
check("E17 re-run invalid scenario -> 404",
      client.post("/api/simulator/rerun/999999", json={"user_id": alex}).status_code == 404)
r = feedback(alex, simulate(alex)["scenario_id"], task_id=999999, actual_hours=5, completed=True)
check("E task not in scenario -> 400", r.status_code == 400)
r = feedback(alex, simulate(alex)["scenario_id"], task_id=assignment, completed=True, deadline_met=False, hours_late=6)
check("E hours late -> delay observation", r.status_code == 201 and
      any(o["observation_type"] == "delay" and o["observed_value"] == 6 for o in r.json()["interpretation"]["observations"]))
r = feedback(alex, simulate(alex)["scenario_id"], task_id=assignment, notes="It took me about 7 hours.", completed=True)
check("E hours read from note ('took 7 hours')", r.status_code == 201 and
      any(o["observed_value"] == 7 for o in r.json()["interpretation"]["observations"]))
r = feedback(alex, simulate(alex)["scenario_id"], notes="I always underestimate assignments because I start late.")
check("E general statement -> no invented number", r.status_code == 201 and r.json()["changes"] == [])

# E9/E10: no Twin yet / very low evidence
fresh, f_assign, _ = make_alex(with_twin=False)
run_f = simulate(fresh)
r = feedback(fresh, run_f["scenario_id"], task_id=f_assign, actual_hours=6.5, completed=True, deadline_met=True)
est = next(c for c in r.json()["changes"] if c["trait_name"] == "task_estimation")
check("E9/E10 first observation: evidence 0 -> 1, still no value", r.status_code == 201 and
      est["evidence_before"] == 0 and est["evidence_after"] == 1 and est["after_value"] is None
      and "at least 3" in est["reason"])

# E15/E16: task deleted / deadline changed after the scenario
run_d = simulate(fresh)
client.put(f"/api/tasks/{f_assign}", json={"deadline": (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()})
r = feedback(fresh, run_d["scenario_id"], task_id=f_assign, actual_hours=6, completed=True)
check("E16 deadline changed -> noted", r.status_code == 201 and
      any("deadline changed" in n for n in r.json()["interpretation"]["notes"]))
run_del = simulate(fresh)
client.delete(f"/api/tasks/{f_assign}")
r = feedback(fresh, run_del["scenario_id"], task_id=f_assign, actual_hours=6, completed=True)
check("E15 deleted task -> scenario estimate used", r.status_code == 201 and
      any("deleted" in n for n in r.json()["interpretation"]["notes"]))
r = client.post(f"/api/simulator/rerun/{run_del['scenario_id']}", json={"user_id": fresh}).json()
check("E15 re-run after task deleted -> graceful status", r["status"] == "not_enough_data")

# E18: database failure -> nothing half-saved
from app.services import feedback_learning  # noqa: E402

run_t = simulate(alex)
count_before = len(client.get(f"/api/observations/user/{alex}?limit=500").json())
original = feedback_learning.diff
feedback_learning.diff = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
try:
    try:
        feedback(alex, run_t["scenario_id"], task_id=assignment, actual_hours=6, completed=True)
        crashed = False
    except RuntimeError:
        crashed = True
finally:
    feedback_learning.diff = original
check("E18 failure mid-update rolls back (no new observations)", crashed and
      len(client.get(f"/api/observations/user/{alex}?limit=500").json()) == count_before)
r = feedback(alex, run_t["scenario_id"], task_id=assignment, actual_hours=6, completed=True)
check("E18 same feedback succeeds afterwards (feedback row was rolled back too)", r.status_code == 201, r.text)

# ---- TEST 8: existing functionality
check("T8 /api/health", client.get("/api/health").json()["status"] == "ok")
check("T8 dashboard / goals / tasks / preferences",
      client.get(f"/api/dashboard/{alex}").status_code == 200 and client.get(f"/api/goals/user/{alex}").status_code == 200
      and client.get(f"/api/tasks/user/{alex}").status_code == 200 and client.get(f"/api/preferences/{alex}").status_code == 200)
check("T8 Digital Twin", len(client.get(f"/api/twin/{alex}/traits").json()["traits"]) == 7)
check("T8 What-If still works", client.post("/api/simulator/run", json={"user_id": alex, "question": "What if I study more tomorrow?"}).json()["status"] == "clarification_needed")

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED: {failures}"))
client.close()
from app.database import engine  # noqa: E402

engine.dispose()
os.remove(TEST_DB)
sys.exit(1 if failures else 0)
