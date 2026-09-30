"""Phase 6 checks - run from the backend/ folder:   python test_phase6.py

Privacy & data control: permissions really change backend behavior, pause/resume learning, forget,
data used, export, access logs, ownership checks - plus the full Phase 1-5 flow.
Uses its own throwaway database (test_phase6.db); your real twinmate.db is never touched.
"""
import json
import os
import sys
from datetime import datetime, timedelta

TEST_DB = "test_phase6.db"
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)
os.environ["DATABASE_URL"] = f"sqlite:///./{TEST_DB}"
os.environ["LLM_PROVIDER"] = "none"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)
failures = []
QUESTION = "What if I spend tomorrow only preparing for my exam and postpone my assignment?"


def check(name, condition, info=""):
    print(("PASS " if condition else "FAIL ") + name + (f"  -> {info}" if info and not condition else ""))
    if not condition:
        failures.append(name)


def H(uid):
    return {"X-User-Id": str(uid)}


def make_alex():
    uid = client.post("/api/users", json={"name": "Alex"}).json()["id"]
    exam_goal = client.post("/api/goals", json={"user_id": uid, "title": "Pass the semester finals", "priority": "high"}).json()["id"]
    six_pm = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
    a = client.post("/api/tasks", json={"user_id": uid, "title": "ML Assignment", "estimated_hours": 5,
                                        "deadline": (six_pm + timedelta(days=1)).isoformat(), "priority": "high"}).json()["id"]
    client.post("/api/tasks", json={"user_id": uid, "goal_id": exam_goal, "title": "ML Exam Preparation",
                                    "estimated_hours": 8, "deadline": (six_pm + timedelta(days=3)).isoformat(),
                                    "priority": "high"})
    client.put(f"/api/preferences/{uid}", json={"available_hours_per_day": 6, "preferred_working_time": "Morning"})
    client.post(f"/api/demo/seed/{uid}")
    client.post(f"/api/twin/{uid}/analyze")
    return uid, a


def run(uid, question=QUESTION):
    return client.post("/api/simulator/run", json={"user_id": uid, "question": question}).json()


def set_perm(uid, **values):
    return client.put(f"/api/privacy/{uid}/permissions", json=values, headers=H(uid))


def traits(uid):
    return {t["trait_name"]: t for t in client.get(f"/api/twin/{uid}/traits").json()["traits"]}


def logs(uid):
    return [l["action"] for l in client.get(f"/api/privacy/{uid}/access-logs?limit=100", headers=H(uid)).json()]


alex, assignment = make_alex()

# ---- TEST 1-7: Phase 1-5 still work
check("T1 health", client.get("/api/health").json()["status"] == "ok")
check("T2 dashboard", client.get(f"/api/dashboard/{alex}").json()["tasks_count"] == 2)
check("T3 Digital Twin traits", traits(alex)["productivity_morning"]["trait_value"] is not None)
r1 = run(alex)
check("T4 What-If works", r1["status"] == "ok" and len(r1["plans"]) == 3 and r1["scenario_id"])
fb = client.post("/api/feedback", json={"user_id": alex, "scenario_id": r1["scenario_id"], "rating": "partially_helpful",
                                        "task_id": assignment, "actual_hours": 6.5, "completed": True, "deadline_met": True})
check("T5 feedback updates Twin", fb.status_code == 201 and fb.json()["updated"] is True)
check("T6 Twin Diff before/after", any(c["trait_name"] == "task_estimation" and c["before_short"] != c["after_short"]
                                        for c in fb.json()["changes"]))
rr = client.post(f"/api/simulator/rerun/{r1['scenario_id']}", json={"user_id": alex}).json()
check("T7 re-run uses updated Twin", rr["learning_effect"]["twin_changes"] != [])

# ---- privacy basics
p = client.get(f"/api/privacy/{alex}", headers=H(alex)).json()
check("Default: all permissions ON, learning on", all(p["permissions"].values()) and not p["learning_paused"])
check("Inventory shows real counts", p["inventory"]["tasks"] == 2 and p["inventory"]["observations"] > 0)

# ---- TEST 8: Behavioral Patterns OFF -> no learned trait used
check("T8 permission change saved", set_perm(alex, behavior=False).json()["permissions"]["behavior"] is False)
r = run(alex)
used = {i["label"]: i for i in r["twin_data_used"]}
check("T8 no learned trait used", r["status"] == "ok" and
      all(i["source"] != "twin" for i in r["twin_data_used"]), [i["source"] for i in r["twin_data_used"]])
check("T8 marked not permitted", used["Task estimation tendency"]["source"] == "not_permitted")
check("T8 estimates used as-is (ratio 1.0)", r["plans"][0]["tasks"][0]["adjusted_required_hours"] == 5.0)
check("T8 limited-evidence message explains why", r["confidence"]["limited_evidence"]
      and "permission is off" in r["confidence"]["message"])
beh = next(c for c in r["data_used"] if c["key"] == "behavior")
check("T8 data used says not permitted", beh["permitted"] is False and beh["items"] == [])
check("T19 duplicate permission update -> no change message",
      "No changes" in set_perm(alex, behavior=False).json()["message"])
set_perm(alex, behavior=True)
check("T8 back ON -> traits used again", any(i["source"] == "twin" for i in run(alex)["twin_data_used"]))

# preferences / goals / timetable / tasks OFF
set_perm(alex, preferences=False)
r = run(alex)
pref_item = next(i for i in r["twin_data_used"] if i["label"] == "Preferred working time")
check("Preferences OFF -> preferred time not used", pref_item["source"] == "not_permitted")
set_perm(alex, preferences=True, goals=False)
GOAL_Q = "What if I work only on my semester goal tomorrow?"  # "semester" appears only in the GOAL title
d = client.post("/api/simulator/analyze", json={"user_id": alex, "question": GOAL_Q}).json()
check("Goals OFF -> goal title not used to recognise tasks", d["status"] == "clarification_needed", d)
set_perm(alex, goals=True)
d = client.post("/api/simulator/analyze", json={"user_id": alex, "question": GOAL_Q}).json()
check("Goals ON -> goal title recognises the exam task", d["status"] == "ok"
      and d["intent"]["focus_task_title"] == "ML Exam Preparation", d)
set_perm(alex, timetable=False)
r = run(alex)
check("Timetable OFF -> cannot simulate, says why", r["status"] == "not_enough_data" and "Timetable" in r["message"])
set_perm(alex, timetable=True, tasks=False)
check("Tasks OFF -> cannot simulate, says why", "Tasks & Deadlines" in run(alex)["message"])
set_perm(alex, tasks=True)
none_on = set_perm(alex, timetable=False, goals=False, tasks=False, history=False, preferences=False, behavior=False)
check("E1 no permissions enabled -> graceful", none_on.status_code == 200 and run(alex)["status"] == "not_enough_data")
set_perm(alex, timetable=True, goals=True, tasks=True, history=True, preferences=True, behavior=True)

# ---- TEST 9: pause learning
check("T9 pause", client.put(f"/api/privacy/{alex}/learning", json={"paused": True}, headers=H(alex)).json()["learning_paused"])
before = traits(alex)
r = run(alex)
fb = client.post("/api/feedback", json={"user_id": alex, "scenario_id": r["scenario_id"], "rating": "helpful",
                                        "task_id": assignment, "actual_hours": 9, "completed": True})
check("T9 feedback stored while paused", fb.status_code == 201 and fb.json()["learning_blocked"])
check("T9 Twin traits unchanged", traits(alex) == before)
check("T9 manual 'Update Twin' refused (409)", client.post(f"/api/twin/{alex}/analyze").status_code == 409)
check("T9 existing Twin still used", any(i["source"] == "twin" for i in run(alex)["twin_data_used"]))

# ---- TEST 10: resume
check("T10 resume", "Learning resumed" in client.put(f"/api/privacy/{alex}/learning", json={"paused": False},
                                                     headers=H(alex)).json()["message"])
r = run(alex)
fb = client.post("/api/feedback", json={"user_id": alex, "scenario_id": r["scenario_id"], "rating": "helpful",
                                        "task_id": assignment, "actual_hours": 9, "completed": True})
check("T10 new observation updates Twin again", fb.json()["updated"] is True and traits(alex) != before)

# history OFF -> no new observations
set_perm(alex, history=False)
check("History OFF -> manual observation refused (403)", client.post("/api/observations", json={
    "user_id": alex, "observation_type": "focus_session", "observed_value": 50}).status_code == 403)
check("History OFF -> Update Twin refused", client.post(f"/api/twin/{alex}/analyze").status_code == 403)
set_perm(alex, history=True)

# ---- data used
du = client.get(f"/api/privacy/{alex}/data-used", headers=H(alex)).json()
tasks_cat = next(c for c in du["categories"] if c["key"] == "tasks")
check("Data used = actual tasks of latest scenario", {i["name"] for i in tasks_cat["items"]} ==
      {"ML Assignment", "ML Exam Preparation"})
check("Data used for unknown scenario -> 404",
      client.get(f"/api/privacy/{alex}/data-used?scenario_id=999999", headers=H(alex)).status_code == 404)

# ---- TEST 12: export
ex = client.get(f"/api/privacy/{alex}/export", headers=H(alex))
data = json.loads(ex.content)
check("T12 export is a JSON download", ex.status_code == 200 and "attachment" in ex.headers["content-disposition"])
check("T12 export has current data", data["user"]["name"] == "Alex" and len(data["tasks"]) == 2
      and data["preferences"]["available_hours_per_day"] == 6 and len(data["twin_traits"]) == 7
      and data["twin_updates"] and data["what_if_history"])
text = ex.text.lower()
check("T12 no secrets / internal ids in export", "api_key" not in text and "llm_" not in text and '"user_id"' not in text)
other, _ = make_alex()
check("T12 export contains only this user's feedback", len(data["feedback"]) == 3)

# ---- TEST 14: security
check("T14 other user's export refused", client.get(f"/api/privacy/{alex}/export", headers=H(other)).status_code == 403)
check("T14 no header refused", client.get(f"/api/privacy/{alex}/export").status_code == 403)
check("T14 other user's logs refused", client.get(f"/api/privacy/{alex}/access-logs", headers=H(other)).status_code == 403)
check("T14 other user's forget refused", client.post(f"/api/privacy/{alex}/forget", json={
    "categories": ["tasks"], "confirm": True}, headers=H(other)).status_code == 403)
check("T14 other user's task change refused",
      client.put(f"/api/tasks/{assignment}", json={"status": "completed"}, headers=H(other)).status_code == 403)
check("T14 other user's scenario feedback refused", client.post("/api/feedback", json={
    "user_id": other, "scenario_id": r1["scenario_id"], "rating": "helpful"}).status_code == 404)

# ---- TEST 13: access logs
actions = logs(alex)
for action in ("twin_viewed", "scenario_run", "recommendation_generated", "feedback_submitted", "twin_updated",
               "permission_changed", "learning_paused", "learning_resumed", "data_used_viewed", "twin_exported"):
    check(f"T13 logged: {action}", action in actions)
newbie = client.post("/api/users", json={"name": "New"}).json()["id"]
check("E18 empty access log for a new user", client.get(f"/api/privacy/{newbie}/access-logs", headers=H(newbie)).json() == [])

# ---- TEST 11: forget (needs confirmation, then really removes)
bad = client.post(f"/api/privacy/{alex}/forget", json={"categories": ["observations"]}, headers=H(alex))
check("T11 forget without confirm refused", bad.status_code == 422 and "confirm" in bad.json()["detail"])
check("T11 invalid category refused", client.post(f"/api/privacy/{alex}/forget", json={
    "categories": ["everything"], "confirm": True}, headers=H(alex)).status_code == 422)
f = client.post(f"/api/privacy/{alex}/forget", json={"categories": ["patterns"], "confirm": True}, headers=H(alex)).json()
check("T11 forget patterns: traits removed, observations kept", f["forgotten"]["twin_traits"] == 7
      and client.get(f"/api/twin/{alex}/traits").json()["traits"] == []
      and client.get(f"/api/privacy/{alex}", headers=H(alex)).json()["inventory"]["observations"] > 0)
check("T11 Twin can be rebuilt from kept observations", client.post(f"/api/twin/{alex}/analyze").status_code == 200)
f = client.post(f"/api/privacy/{alex}/forget", json={"categories": ["observations", "history"], "confirm": True},
                headers=H(alex)).json()
inv = client.get(f"/api/privacy/{alex}", headers=H(alex)).json()["inventory"]
check("T11 forget observations + history really removed",
      inv["observations"] == 0 and inv["feedback"] == 0 and inv["scenario_runs"] == 0 and inv["twin_updates"] == 0)
check("T11 derived traits removed with observations", client.get(f"/api/twin/{alex}/traits").json()["traits"] == [])
check("T11 other user's data untouched", client.get(f"/api/privacy/{other}", headers=H(other)).json()["inventory"]["observations"] > 0)
check("T11 forget logged", "data_forgotten" in logs(alex))
r = run(alex)
check("E3/E8 no Twin traits -> simulation still works with limited evidence", r["status"] == "ok"
      and r["confidence"]["limited_evidence"])
client.post(f"/api/privacy/{alex}/forget", json={"categories": ["tasks", "goals", "preferences"], "confirm": True}, headers=H(alex))
inv = client.get(f"/api/privacy/{alex}", headers=H(alex)).json()["inventory"]
check("T11 tasks/goals/preferences removed", inv["tasks"] == 0 and inv["goals"] == 0 and inv["preferences"] == 0)
check("E5/E6 no tasks/goals -> dashboard still works", client.get(f"/api/dashboard/{alex}").status_code == 200)
ex = json.loads(client.get(f"/api/privacy/{alex}/export", headers=H(alex)).content)
check("E9 export with no data is valid JSON", ex["tasks"] == [] and ex["preferences"] is None)
check("E13 scenario with no data -> graceful status", run(alex)["status"] == "not_enough_data")

# ---- E11/E12: forget failure rolls back everything
from app.services import privacy_service  # noqa: E402

orig = privacy_service.FORGET_ORDER
privacy_service.FORGET_ORDER = ["goals", "boom"]
before_inv = client.get(f"/api/privacy/{other}", headers=H(other)).json()["inventory"]
try:
    import app.models as m  # noqa: E402
    orig_goal = privacy_service.Goal
    privacy_service.Goal = None  # makes the delete step fail
    res = client.post(f"/api/privacy/{other}/forget", json={"categories": ["goals"], "confirm": True}, headers=H(other))
    failed = res.status_code >= 500
except Exception:
    failed = True
finally:
    privacy_service.Goal = orig_goal
    privacy_service.FORGET_ORDER = orig
check("E11 forget failure -> nothing removed", failed and
      client.get(f"/api/privacy/{other}", headers=H(other)).json()["inventory"] == before_inv)

print("\n" + ("ALL CHECKS PASSED" if not failures else f"{len(failures)} CHECK(S) FAILED: {failures}"))
client.close()
from app.database import engine  # noqa: E402

engine.dispose()
os.remove(TEST_DB)
sys.exit(1 if failures else 0)
