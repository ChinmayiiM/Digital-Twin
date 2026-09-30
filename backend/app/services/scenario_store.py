"""Scenario storage (Phase 5).

Phase 4 calculated results but did not keep them. Feedback must point at the scenario that produced the
recommendation, so every successful run is now stored as a ScenarioRun with a compact SUMMARY of its numbers.

The summary is only used for two things:
  * knowing which tasks / plan / Twin values the feedback refers to
  * showing "previous vs current" after a RE-RUN.
A re-run never reuses the stored numbers - it runs the full Phase 4 simulation again with the current Twin.
"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models import ScenarioRun


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def build_summary(result: dict) -> dict:
    intent = result["intent"]
    first_plan = result["plans"][0]
    return {
        "intent": {
            "focus_task_id": intent["focus_task_id"],
            "deferred_task_ids": intent["deferred_task_ids"],
            "time_horizon": intent["time_horizon"],
            "start_date": _iso(intent["start_date"]),
        },
        "tasks": {
            str(t["task_id"]): {"title": t["title"], "estimated_hours": t["estimated_hours"],
                                "deadline": _iso(t["deadline"]), "priority": t["priority"],
                                "adjusted_required_hours": t["adjusted_required_hours"]}
            for t in first_plan["tasks"]
        },
        "plans": {
            p["id"]: {"name": p["name"], "overall_expected": p["overall_expected"],
                      "tasks": {str(t["task_id"]): {"on_time_probability": t["on_time_probability"],
                                                    "expected_progress": t["expected_progress"]}
                                for t in p["tasks"]}}
            for p in result["plans"]
        },
        "recommended_plan_id": result["recommendation"]["recommended_plan_id"],
        "headline": result["recommendation"]["headline"],
        "twin": {i["label"]: {"value": i["value"], "source": i["source"], "confidence": i.get("confidence"),
                              "evidence_count": i.get("evidence_count")}
                 for i in result["twin_data_used"]},
        "confidence": {"label": result["confidence"]["label"], "score": result["confidence"]["score"]},
        "data_used": result.get("data_used", []),  # Phase 6: what this recommendation was based on
    }


def save_run(db: Session, user_id: int, result: dict, parent_id: Optional[int] = None) -> ScenarioRun:
    run = ScenarioRun(user_id=user_id, parent_id=parent_id, question=result["question"],
                      recommended_plan_id=result["recommendation"]["recommended_plan_id"],
                      summary=build_summary(result))
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, user_id: int, scenario_id: int) -> Optional[ScenarioRun]:
    run = db.get(ScenarioRun, scenario_id)
    return run if run is not None and run.user_id == user_id else None


def learning_effect(previous: ScenarioRun, current: dict) -> dict:
    """Compare the stored numbers of the original run with a freshly calculated re-run."""
    before = previous.summary or {}
    after = build_summary(current)

    twin_changes = []
    for label, new in after["twin"].items():
        old = before.get("twin", {}).get(label)
        if old and (old["value"] != new["value"] or old.get("evidence_count") != new.get("evidence_count")):
            twin_changes.append({"label": label, "before": old["value"], "after": new["value"],
                                 "evidence_before": old.get("evidence_count"), "evidence_after": new.get("evidence_count")})

    task_changes = []
    for tid, new in after["tasks"].items():
        old = before.get("tasks", {}).get(tid)
        if old:
            task_changes.append({"task_id": int(tid), "title": new["title"],
                                 "estimated_before": old["estimated_hours"], "estimated_after": new["estimated_hours"],
                                 "adjusted_before": old["adjusted_required_hours"],
                                 "adjusted_after": new["adjusted_required_hours"]})

    plan_changes = []
    for pid, new_plan in after["plans"].items():
        old_plan = before.get("plans", {}).get(pid)
        if not old_plan:
            continue
        for tid, new_task in new_plan["tasks"].items():
            old_task = old_plan["tasks"].get(tid)
            if old_task:
                plan_changes.append({"plan_id": pid, "plan_name": new_plan["name"],
                                     "task_title": after["tasks"][tid]["title"],
                                     "on_time_before": old_task["on_time_probability"],
                                     "on_time_after": new_task["on_time_probability"]})

    same_tasks = set(before.get("tasks", {})) == set(after["tasks"])
    changed_numbers = any(abs(p["on_time_after"] - p["on_time_before"]) >= 0.005 for p in plan_changes) or \
        any(abs(t["adjusted_after"] - t["adjusted_before"]) >= 0.005 for t in task_changes)
    if not twin_changes:
        message = ("Your Twin has not changed since the original run, so the re-calculated results are the same "
                   "(same data, same random seed).")
    elif changed_numbers:
        message = "Your updated Twin was used, and it changed the simulated results."
    else:
        message = "Your updated Twin was used, but the change was too small to move the simulated results."
    if not same_tasks:
        message += " Note: the tasks in this scenario changed since the original run."

    return {
        "previous_scenario_id": previous.id,
        "previous_recommendation": before.get("headline"),
        "current_recommendation": after["headline"],
        "recommendation_changed": before.get("recommended_plan_id") != after["recommended_plan_id"],
        "twin_changes": twin_changes,
        "task_changes": task_changes,
        "plan_changes": plan_changes,
        "message": message,
    }
