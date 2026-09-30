"""Phase 6 - data inventory, FORGET and EXPORT for one user.

SOURCE DATA vs TWIN DATA
    Source data:  tasks, goals, preferences, behavioral observations, scenario/feedback history
    Twin data:    learned traits (value, confidence, evidence) and their before/after snapshots
Twin data is CALCULATED from observations. So:
    forget observations -> the traits and snapshots calculated from them are deleted as well
    forget patterns     -> only the traits/snapshots are deleted; the observations stay, and the Twin can be
                           rebuilt from them later with "Update Twin" (if learning is allowed)
Every forget runs in ONE transaction: either everything selected is removed, or nothing is.
"""
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models import (BehaviorObservation, Feedback, Goal, Permission, Preference, ScenarioRun, Task,
                        TwinSnapshot, TwinTrait, User)
from app.services import pattern_analyzer, permission_gate
from app.services.simulation_config import confidence_label

FORGET_LABELS = {
    "tasks": "Tasks & Deadlines",
    "goals": "Goals",
    "preferences": "Preferences (available hours, working time)",
    "observations": "Behavioral Observations",
    "patterns": "Inferred Patterns (Twin traits)",
    "history": "Study / Work History (what-if runs and feedback)",
}
# Deletion order matters because of foreign keys (feedback -> snapshots, scenarios).
FORGET_ORDER = ["history", "observations", "patterns", "tasks", "goals", "preferences"]


def inventory(db: Session, user_id: int) -> Dict[str, int]:
    def count(model):
        return db.query(model).filter(model.user_id == user_id).count()

    return {
        "goals": count(Goal),
        "tasks": count(Task),
        "preferences": count(Preference),
        "observations": count(BehaviorObservation),
        "traits_with_values": db.query(TwinTrait).filter(TwinTrait.user_id == user_id,
                                                         TwinTrait.sufficient_evidence.is_(True)).count(),
        "scenario_runs": count(ScenarioRun),
        "feedback": count(Feedback),
        "twin_updates": count(TwinSnapshot),
    }


def forget(db: Session, user_id: int, categories: List[str]) -> dict:
    removed, notes = {}, []

    def delete(model, key):
        removed[key] = removed.get(key, 0) + db.query(model).filter(model.user_id == user_id).delete(
            synchronize_session=False)

    try:
        for category in [c for c in FORGET_ORDER if c in categories]:
            if category == "history":
                delete(Feedback, "feedback")  # also removes their snapshots (ON DELETE CASCADE)
                delete(TwinSnapshot, "twin_updates")
                delete(ScenarioRun, "scenario_runs")
            elif category == "observations":
                delete(BehaviorObservation, "observations")
                delete(TwinTrait, "twin_traits")  # calculated from the deleted observations
                delete(TwinSnapshot, "twin_updates")
                notes.append("Twin traits and Twin updates calculated from these observations were removed too.")
            elif category == "patterns":
                delete(TwinTrait, "twin_traits")
                delete(TwinSnapshot, "twin_updates")
                notes.append("Your observations were kept. Click 'Update Twin' on the Digital Twin page to rebuild "
                             "traits from them (only while learning is allowed).")
            elif category == "tasks":
                delete(Task, "tasks")
                if "history" not in categories:
                    notes.append("Past what-if runs and feedback still mention these tasks; forget 'Study / Work "
                                 "History' as well to remove them.")
            elif category == "goals":
                delete(Goal, "goals")  # tasks stay; their goal link becomes empty
            elif category == "preferences":
                delete(Preference, "preferences")
                notes.append("TwinMate needs your available hours to simulate decisions; set them again to use the "
                             "What-If Simulator.")
        db.commit()
    except Exception:
        db.rollback()
        raise

    total = sum(removed.values())
    labels = ", ".join(FORGET_LABELS[c] for c in categories)
    message = (f"TwinMate forgot: {labels}. {total} record(s) were permanently removed." if total
               else f"There was nothing stored for: {labels}.")
    return {"forgotten": removed, "message": message, "notes": notes}


def _iso(value):
    return value.isoformat() if value is not None else None


def export(db: Session, user_id: int) -> dict:
    """All of the user's own data as plain JSON. No internal ids, no other users, no settings or secrets."""
    user = db.get(User, user_id)
    perms = permission_gate.get_or_create(db, user_id)
    pref = db.query(Preference).filter(Preference.user_id == user_id).first()
    goals = db.query(Goal).filter(Goal.user_id == user_id).order_by(Goal.id).all()
    tasks = db.query(Task).filter(Task.user_id == user_id).order_by(Task.id).all()
    traits = pattern_analyzer.get_traits(db, user_id)
    observations = db.query(BehaviorObservation).filter(BehaviorObservation.user_id == user_id).all()
    feedback = db.query(Feedback).filter(Feedback.user_id == user_id).order_by(Feedback.id).all()
    updates = db.query(TwinSnapshot).filter(TwinSnapshot.user_id == user_id).order_by(TwinSnapshot.id).all()
    runs = db.query(ScenarioRun).filter(ScenarioRun.user_id == user_id).order_by(ScenarioRun.id).all()
    goal_titles = {g.id: g.title for g in goals}

    summary: Dict[str, Dict[str, int]] = {}
    for o in observations:
        entry = summary.setdefault(o.observation_type, {"total": 0, "synthetic_demo": 0, "from_feedback": 0})
        entry["total"] += 1
        entry["synthetic_demo"] += int(o.source == "demo")
        entry["from_feedback"] += int(o.source == "feedback")

    return {
        "export_version": "1.0",
        "generated_at": _iso(pattern_analyzer.utc_now()) + "Z",
        "user": {"name": user.name, "member_since": _iso(user.created_at)},
        "permissions": permission_gate.as_dict(perms),
        "learning_paused": bool(perms.learning_paused),
        "preferences": ({"available_hours_per_day": pref.available_hours_per_day,
                         "preferred_working_time": pref.preferred_working_time} if pref else None),
        "goals": [{"title": g.title, "description": g.description, "priority": g.priority} for g in goals],
        "tasks": [{"title": t.title, "description": t.description, "goal": goal_titles.get(t.goal_id),
                   "estimated_hours": t.estimated_hours, "deadline": _iso(t.deadline), "priority": t.priority,
                   "status": t.status} for t in tasks],
        "twin_traits": [{"name": t.trait_name, "label": t.display_name, "value": t.trait_value,
                         "display_value": t.display_value, "confidence": t.confidence,
                         "confidence_label": confidence_label(t.confidence), "evidence": t.evidence_count,
                         "enough_evidence": t.sufficient_evidence, "explanation": t.description,
                         "last_updated": _iso(t.last_updated)} for t in traits],
        "behavioral_summary": [{"observation_type": k, **v} for k, v in sorted(summary.items())],
        "feedback": [{"rating": f.rating, "reasons": f.reasons, "task": f.task_title, "actual_hours": f.actual_hours,
                      "completed": f.completed, "deadline_met": f.deadline_met, "notes": f.notes,
                      "created_at": _iso(f.created_at)} for f in feedback],
        "twin_updates": [{"created_at": _iso(u.created_at), "reason": u.reason,
                          "changes": [{"trait": c["label"], "before": c["before_short"], "after": c["after_short"],
                                       "evidence_before": c["evidence_before"], "evidence_after": c["evidence_after"],
                                       "reason": c["reason"]} for c in u.changes]} for u in updates],
        "what_if_history": [{"question": r.question, "recommendation": (r.summary or {}).get("headline"),
                             "created_at": _iso(r.created_at)} for r in runs],
    }
