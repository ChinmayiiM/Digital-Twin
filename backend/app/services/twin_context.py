"""Twin context: collects everything the What-If simulator needs about ONE user.

It only READS existing Phase 2/3 data:
    preferences      -> available hours per day, preferred working time   (what the user SAID)
    twin_traits      -> productivity, estimation ratio, procrastination     (what the Twin LEARNED)
    behavior_observations -> only used to measure how much the values vary (for Monte Carlo)

Nothing is invented. When a trait has "Not enough evidence yet", the simulator uses a clearly
labelled NEUTRAL fallback (it assumes "no adjustment") and the result is marked as limited evidence.

Phase 6 - PERMISSION GATE: this is the ONLY place the simulator reads user data, so the permissions are
applied here. A category that is switched off is simply not loaded:
    timetable OFF   -> no available hours        (the simulator cannot run and says why)
    tasks OFF       -> no tasks                  (the simulator cannot run and says why)
    goals OFF       -> goal titles are not used to recognise tasks in the question
    preferences OFF -> preferred working time is ignored (day order from observed productivity instead)
    behavior OFF    -> no learned Twin trait is used; neutral values, marked "not permitted"
"""
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from app.models import BehaviorObservation, Preference, Task
from app.services import pattern_analyzer, permission_gate

PERIODS = ("morning", "afternoon", "evening")

# ---- Neutral fallbacks (used ONLY when the Twin has no sufficient evidence) ----
FALLBACK_PRODUCTIVITY = 0.70  # only used when NO period has evidence; it then cancels out (factor 1.0)
FALLBACK_ESTIMATION_RATIO = 1.0  # "tasks take as long as estimated"
FALLBACK_PROCRASTINATION = 0.0  # "no time lost to delays"

# ---- Spread (standard deviation) used by Monte Carlo when there is too little data to measure it ----
FALLBACK_PRODUCTIVITY_SD = 0.10
FALLBACK_ESTIMATION_SD = 0.20
MIN_PRODUCTIVITY_SD = 0.03
MIN_ESTIMATION_SD = 0.05

# Order in which the day's hours are spent, starting from the stated preference.
PERIOD_ORDER = {
    "Morning": ["morning", "afternoon", "evening"],
    "Afternoon": ["afternoon", "evening", "morning"],
    "Evening": ["evening", "afternoon", "morning"],
}


def _std(values: List[float]) -> Optional[float]:
    return float(np.std(values)) if len(values) >= 2 else None


def _widen(sd: float, confidence: float) -> float:
    """Less evidence -> wider Monte Carlo spread. Full confidence keeps sd, zero confidence doubles it."""
    return sd * (2.0 - confidence)


def _trait_info(trait, label: str, used_value: float, source: str, used_for: str) -> dict:
    if source == "not_permitted":
        trait = None  # nothing from the stored trait is shown or used
    return {
        "name": trait.trait_name if trait else None,
        "label": label,
        "display_value": trait.display_value if trait else "Not enough evidence yet",
        "used_value": used_value,
        "source": source,  # "twin" (learned) or "fallback" (neutral assumption)
        "confidence": float(trait.confidence) if trait else 0.0,
        "evidence_count": int(trait.evidence_count) if trait else 0,
        "used_for": used_for,
    }


def build_context(db: Session, user_id: int) -> dict:
    allowed = permission_gate.as_dict(permission_gate.get_or_create(db, user_id))
    pref = db.query(Preference).filter(Preference.user_id == user_id).first() if allowed["timetable"] or allowed["preferences"] else None
    traits = {t.trait_name: t for t in pattern_analyzer.get_traits(db, user_id)} if allowed["behavior"] else {}
    observations = (db.query(BehaviorObservation).filter(BehaviorObservation.user_id == user_id).all()
                    if allowed["behavior"] else [])
    open_tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.status != "completed")
        .order_by(Task.deadline.is_(None), Task.deadline, Task.id)
        .all()
    ) if allowed["tasks"] else []
    missing = "not_permitted" if not allowed["behavior"] else "fallback"  # source label for unusable traits

    def usable(name):
        t = traits.get(name)
        return t if (t is not None and t.sufficient_evidence and t.trait_value is not None) else None

    # ---------------- productivity by time of day ----------------
    known = {p: usable(f"productivity_{p}") for p in PERIODS}
    known_values = [t.trait_value for t in known.values() if t]
    # Reference = the user's OWN average productivity. Estimation ratios were measured at "normal"
    # productivity, so productivity is applied RELATIVE to this average (avoids counting it twice).
    reference = float(np.mean(known_values)) if known_values else FALLBACK_PRODUCTIVITY

    productivity = {}
    for p in PERIODS:
        trait = known[p]
        values = [o.observed_value for o in observations
                  if o.observation_type == "working_time" and (o.context or {}).get("time_period") == p]
        if trait:
            sd = max(MIN_PRODUCTIVITY_SD, _std(values) or FALLBACK_PRODUCTIVITY_SD)
            productivity[p] = {
                "mean": float(trait.trait_value),
                "sd": _widen(sd, trait.confidence),
                "info": _trait_info(trait, f"{p.capitalize()} productivity", float(trait.trait_value), "twin",
                                    f"speed of work during the {p}"),
            }
        else:
            productivity[p] = {
                "mean": reference,  # neutral: same as the user's average -> factor 1.0
                "sd": _widen(FALLBACK_PRODUCTIVITY_SD, 0.0),
                "info": _trait_info(traits.get(f"productivity_{p}"), f"{p.capitalize()} productivity", reference,
                                    missing, f"speed of work during the {p} (neutral assumption)"),
            }

    # ---------------- estimation tendency ----------------
    est = usable("task_estimation")
    ratios = []
    for o in observations:
        if o.observation_type == "task_estimation":
            e = (o.context or {}).get("estimated_hours")
            if isinstance(e, (int, float)) and e > 0:
                ratios.append(o.observed_value / e)
    if est:
        est_sd = _widen(max(MIN_ESTIMATION_SD, _std(ratios) or FALLBACK_ESTIMATION_SD), est.confidence)
        estimation = {"ratio": float(est.trait_value), "sd": est_sd,
                      "info": _trait_info(est, "Task estimation tendency", float(est.trait_value), "twin",
                                          "adjusting your time estimates")}
    else:
        estimation = {"ratio": FALLBACK_ESTIMATION_RATIO, "sd": _widen(FALLBACK_ESTIMATION_SD, 0.0),
                      "info": _trait_info(traits.get("task_estimation"), "Task estimation tendency",
                                          FALLBACK_ESTIMATION_RATIO, missing,
                                          "adjusting your time estimates (neutral: estimates used as-is)")}

    # ---------------- procrastination (task-delay score 0..1) ----------------
    proc = usable("procrastination")
    procrastination = {
        "score": float(proc.trait_value) if proc else FALLBACK_PROCRASTINATION,
        "info": _trait_info(proc or traits.get("procrastination"), "Procrastination tendency",
                            float(proc.trait_value) if proc else FALLBACK_PROCRASTINATION,
                            "twin" if proc else missing,
                            "chance of losing time to delays each day" + ("" if proc else " (neutral: none assumed)")),
    }

    # ---------------- task ordering habit (used only as a small bonus in the recommender) ----------------
    order = usable("task_ordering")
    ordering = None
    if order and (order.details or {}).get("preference"):
        ordering = {"preference": order.details["preference"],
                    "info": _trait_info(order, "Preferred task ordering", float(order.trait_value), "twin",
                                        "checking whether a plan matches your habits")}

    preferred = pref.preferred_working_time if (pref and allowed["preferences"]) else None
    if preferred in PERIOD_ORDER:
        period_order = PERIOD_ORDER[preferred]
    else:  # "Flexible" (or unknown): start with the period where the Twin observed the highest productivity
        period_order = sorted(PERIODS, key=lambda p: productivity[p]["mean"], reverse=True)

    return {
        "user_id": user_id,
        "permissions": allowed,
        "use_goals": allowed["goals"],
        "has_preferences": pref is not None and allowed["timetable"],
        "available_hours": float(pref.available_hours_per_day) if (pref and allowed["timetable"]) else None,
        "preferred_working_time": preferred,
        "period_order": period_order,
        "reference_productivity": reference,
        "productivity": productivity,
        "estimation": estimation,
        "procrastination": procrastination,
        "ordering": ordering,
        "twin_analyzed": bool(traits),
        "open_tasks": open_tasks,
    }
