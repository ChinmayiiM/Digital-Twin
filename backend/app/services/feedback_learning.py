"""Phase 5 - the LEARNING LOOP: feedback -> interpretation -> observations -> Twin update -> Twin Diff.

HOW THE TWIN LEARNS (plain Python, no LLM)
    1. Feedback is only turned into an observation when it contains real behavioral EVIDENCE:
         actual hours of a COMPLETED task   -> task_estimation observation   (actual / estimated)
         finished on time / hours late       -> delay observation             (feeds procrastination)
    2. The observation is stored like any Phase 3 observation (source = "feedback").
    3. The Phase 3 Pattern Analyzer re-reads all observations in time order. Because the feedback is the
       newest one, this is exactly the architecture formula for that trait:
             new_value = old_value + ALPHA x (observed_value - old_value)          (ALPHA = 0.2)
       Evidence count goes up by one per observation, confidence = min(1, evidence / 10) (Phase 3 logic).
    4. The Twin before and after is saved as a TwinSnapshot and the differences become the Twin Diff.

WHAT DOES NOT CHANGE THE TWIN
    ratings (opinions), preferences ("I prefer nights"), changed schedules/deadlines, general statements
    without numbers, unfinished tasks (total time unknown). They are stored and explained, nothing more.

Everything happens in ONE database transaction: feedback + observations + traits + snapshot are saved
together, or (on any error) nothing is saved.
"""
import re
from typing import Dict, List, Optional

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.models import BehaviorObservation, Feedback, Task, TwinSnapshot
from app.models.twin_trait import TRAIT_LABELS, TRAIT_ORDER
from app.services import llm_client, pattern_analyzer, permission_gate
from app.services.pattern_analyzer import ALPHA, utc_now
from app.services.simulation_config import confidence_label

MIN_RATIO, MAX_RATIO = 0.1, 10.0  # actual/estimated outside this range is rejected as unrealistic
SIGNIFICANT = {"focus_capacity": 0.5}  # minutes; every other numeric trait uses 0.005


class FeedbackError(Exception):
    """A problem the user can fix (shown as a readable message). status_code follows HTTP meaning."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ------------------------------------------------------------------ reading free-text notes
_TOOK_HOURS = re.compile(
    r"\b(?:took|spent|needed|required|it was)\s+(?:me\s+)?(?:about\s+|around\s+|roughly\s+|nearly\s+|almost\s+)?"
    r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b", re.IGNORECASE)
_CATEGORY_WORDS = {
    "preference": ("prefer", "i like", "rather", "i enjoy", "i love"),
    "circumstance_change": ("schedule", "plans changed", "last minute", "last-minute", "emergency", "sick",
                            "deadline changed", "deadline was moved", "extended", "postponed by"),
    "behavior_report": ("took", "longer", "faster", "underestimate", "overestimate", "procrastinat", "late", "spent"),
}


class _LLMNote(BaseModel):
    category: str
    actual_hours_stated: Optional[float] = None


def _rules_notes(notes: str) -> dict:
    lowered = notes.lower()
    category = next((c for c, words in _CATEGORY_WORDS.items() if any(w in lowered for w in words)), "other")
    found = {float(m) for m in _TOOK_HOURS.findall(notes)}
    return {"category": category, "hours": found.pop() if len(found) == 1 else None, "by": "rules"}


def _llm_notes(notes: str) -> Optional[dict]:
    """Optional: LLM classifies the note and extracts an hour number the user STATED. Python checks that the
    number really appears in the note - the LLM can never invent a value."""
    reply = llm_client.complete(
        "Classify a student's feedback note. Reply with ONE JSON object only: "
        '{"category": "behavior_report" | "preference" | "circumstance_change" | "other", '
        '"actual_hours_stated": number or null}. actual_hours_stated is only the number of hours the note says '
        "a task actually took; null if the note does not state it. Do not estimate or calculate.",
        notes, max_tokens=100)
    data = llm_client.extract_json(reply)
    if data is None:
        return None
    try:
        parsed = _LLMNote.model_validate(data)
    except ValidationError:
        return None
    if parsed.category not in ("behavior_report", "preference", "circumstance_change", "other"):
        return None
    hours = parsed.actual_hours_stated
    if hours is not None and f"{hours:g}" not in re.findall(r"\d+(?:\.\d+)?", notes):
        hours = None  # not literally in the note -> ignore
    return {"category": parsed.category, "hours": hours, "by": "llm"}


def read_notes(notes: Optional[str]) -> dict:
    if not notes:
        return {"category": None, "hours": None, "by": "rules"}
    return _llm_notes(notes) or _rules_notes(notes)


# ------------------------------------------------------------------ interpretation (no database)
def interpret(payload, estimated_hours: Optional[float], task_title: Optional[str]) -> dict:
    """Decide which observations the feedback supports. Returns {"specs": [...], "notes": [...], ...}."""
    specs, notes = [], []
    note_info = read_notes(payload.notes)
    reasons = set(payload.reasons)

    actual = payload.actual_hours
    if actual is None and note_info["hours"] is not None and payload.task_id is not None:
        actual = note_info["hours"]
        notes.append(f"Actual time {actual:g} h was read from your note.")

    # ---- estimation evidence: only a COMPLETED task has a known total time
    if actual is not None and estimated_hours:
        if payload.completed is True:
            ratio = actual / estimated_hours
            if not MIN_RATIO <= ratio <= MAX_RATIO:
                raise FeedbackError(
                    f"{actual:g} h compared with the {estimated_hours:g} h estimate (x{ratio:.1f}) looks unrealistic. "
                    "Please check the actual hours.", 422)
            specs.append({"type": "task_estimation", "value": float(actual), "ratio": ratio,
                          "context": {"estimated_hours": float(estimated_hours)},
                          "text": f"{task_title} took {actual:g} h vs {estimated_hours:g} h estimated "
                                  f"(ratio {ratio:.2f})"})
            if "task_took_longer" in reasons and ratio < 1:
                notes.append("You selected 'took longer', but the actual hours are below the estimate - "
                             "TwinMate used the numbers.")
            if "task_faster" in reasons and ratio > 1:
                notes.append("You selected 'finished faster', but the actual hours are above the estimate - "
                             "TwinMate used the numbers.")
        else:
            notes.append("The task is not marked as completed, so its total time is still unknown - "
                         "the estimation tendency was not changed.")
    elif reasons & {"task_took_longer", "task_faster", "estimate_accurate"}:
        notes.append("To learn your estimation tendency, TwinMate needs the actual hours of a completed task. "
                     "The reason was stored.")

    # ---- deadline evidence (feeds the procrastination / task-delay trait)
    if payload.completed is True and payload.deadline_met is True:
        specs.append({"type": "delay", "value": 0.0, "context": {},
                      "text": f"{task_title} was finished on time (0 h late)"})
    elif payload.completed is True and payload.deadline_met is False:
        if payload.hours_late is not None:
            specs.append({"type": "delay", "value": float(payload.hours_late), "context": {},
                          "text": f"{task_title} was finished {payload.hours_late:g} h after the deadline"})
        else:
            notes.append("Deadline missed, but without the number of hours late the delay trait cannot be updated.")
    elif payload.completed is False and payload.deadline_met is False:
        notes.append("The task is not finished yet, so the final delay is unknown - no delay update.")

    # ---- things that are stored but never change behavioral traits
    if reasons & {"schedule_changed", "deadline_changed"} or note_info["category"] == "circumstance_change":
        notes.append("A changed schedule or deadline describes your circumstances, not how you work - "
                     "no trait was changed because of it.")
    if "prefer_other_option" in reasons or note_info["category"] == "preference":
        notes.append("Preferences are stored but do not change observed behavior (what you prefer is kept "
                     "separate from how you actually work).")
    if note_info["category"] == "behavior_report" and not specs:
        notes.append("Your note describes your behavior, but TwinMate only updates traits from measured outcomes "
                     "(for example actual hours), not from general statements.")
    notes.append("Your rating is stored as feedback on the recommendation; ratings do not change behavioral traits.")

    return {"specs": specs, "notes": notes, "note_category": note_info["category"], "understood_by": note_info["by"]}


# ------------------------------------------------------------------ Twin snapshot + diff
def _snapshot(traits) -> Dict[str, dict]:
    return {t.trait_name: {"value": t.trait_value, "display": t.display_value, "confidence": float(t.confidence),
                           "evidence_count": int(t.evidence_count), "sufficient": bool(t.sufficient_evidence),
                           "preference": (t.details or {}).get("preference")}
            for t in traits}


def short_value(name: str, value: Optional[float], display: str) -> str:
    if value is None:
        return display if name == "task_ordering" and display else "No value yet"
    if name.startswith("productivity_"):
        return f"{round(value * 100)}%"
    if name == "task_estimation":
        pct = round((value - 1) * 100)
        return f"{pct:+d}%" if pct else "±0%"
    if name == "focus_capacity":
        return f"{round(value)} min"
    if name == "procrastination":
        return f"{value:.2f} ({display})"
    return display


_EMPTY = {"value": None, "display": "Not analyzed yet", "confidence": 0.0, "evidence_count": 0,
          "sufficient": False, "preference": None}
_SPEC_FOR_TRAIT = {"task_estimation": "task_estimation", "procrastination": "delay"}


def _observed_for_trait(name: str, spec: dict) -> float:
    """The observed value in the trait's own unit (what goes into the formula)."""
    if name == "task_estimation":
        return spec["ratio"]
    return min(1.0, spec["value"] / 24)  # procrastination: delay score, a full day late = 1.0


def delta_hint(old_value: float, observed: float) -> str:
    return "down" if observed < old_value else "up" if observed > old_value else ""


def diff(before: Dict[str, dict], after: Dict[str, dict], specs: List[dict], pending: int) -> List[dict]:
    changes = []
    for name in TRAIT_ORDER:
        b, a = before.get(name, _EMPTY), after.get(name, _EMPTY)
        value_changed = (b["value"] is None) != (a["value"] is None) or (
            b["value"] is not None and abs(a["value"] - b["value"]) > 1e-9)
        if not (value_changed or b["evidence_count"] != a["evidence_count"] or b["display"] != a["display"]):
            continue

        spec = next((s for s in specs if s["type"] == _SPEC_FOR_TRAIT.get(name)), None)
        formula = None
        if spec and b["sufficient"] and a["sufficient"] and b["value"] is not None and a["value"] is not None:
            observed = _observed_for_trait(name, spec)
            expected = b["value"] + ALPHA * (observed - b["value"])
            formula = (f"{b['value']:.4f} + {ALPHA} x ({observed:.4f} - {b['value']:.4f}) = {expected:.4f}")
            if abs(expected - a["value"]) > 0.0006:
                formula += " (the analyzer also re-read earlier observations, so the stored value differs slightly)"

        if spec:
            reason = f"Your feedback: {spec['text']}."
            if name == "task_estimation" and b["value"] is not None and delta_hint(b["value"], spec["ratio"]):
                expected_hours = spec["context"]["estimated_hours"] * b["value"]
                reason += (f" Your Twin expected about {expected_hours:.1f} h (x{b['value']:.2f}), so the tendency moves "
                           f"{delta_hint(b['value'], spec['ratio'])} toward what really happened.")
            if not a["sufficient"]:
                reason += (f" Evidence grew to {a['evidence_count']}; at least {pattern_analyzer.MIN_EVIDENCE} "
                           "observations are needed before a value is shown.")
            elif not b["sufficient"]:
                reason += f" This trait now has enough evidence ({a['evidence_count']} observations) to report a value."
        else:
            reason = (f"Re-read {pending} observation(s) that were stored earlier but not analyzed yet."
                      if pending else "Recalculated from your stored observations.")

        threshold = SIGNIFICANT.get(name, 0.005)
        delta = (a["value"] - b["value"]) if (a["value"] is not None and b["value"] is not None) else None
        significant = (b["evidence_count"] != a["evidence_count"] or (delta is not None and abs(delta) >= threshold)
                       or b["sufficient"] != a["sufficient"])
        changes.append({
            "trait_name": name, "label": TRAIT_LABELS[name],
            "before_value": b["value"], "after_value": a["value"],
            "change": round(delta, 4) if delta is not None else None,
            "before_short": short_value(name, b["value"], b["display"]),
            "after_short": short_value(name, a["value"], a["display"]),
            "confidence_before": b["confidence"], "confidence_after": a["confidence"],
            "confidence_label_before": confidence_label(b["confidence"]),
            "confidence_label_after": confidence_label(a["confidence"]),
            "evidence_before": b["evidence_count"], "evidence_after": a["evidence_count"],
            "significant": significant, "reason": reason, "formula": formula,
        })
    return changes


# ------------------------------------------------------------------ main entry point
def submit(db: Session, payload, scenario) -> dict:
    summary = scenario.summary or {}
    task_info, task_notes, linked_task_id = None, [], None
    if payload.task_id is not None:
        task_info = summary.get("tasks", {}).get(str(payload.task_id))
        if task_info is None:
            raise FeedbackError("This task was not part of the scenario you are giving feedback on.")
        current = db.get(Task, payload.task_id)
        if current is None or current.user_id != payload.user_id:
            task_notes.append("This task was deleted after the scenario; the estimate stored with the scenario was used.")
        else:
            linked_task_id = current.id  # only link rows to a task that still exists
            if current.estimated_hours != task_info["estimated_hours"]:
                task_notes.append(f"The task's estimate changed after the scenario (now {current.estimated_hours:g} h); "
                                  f"the estimate used in the scenario ({task_info['estimated_hours']:g} h) was used.")
            if current.deadline and task_info.get("deadline") and current.deadline.isoformat() != task_info["deadline"]:
                task_notes.append("The task's deadline changed after the scenario; this feedback still refers to the "
                                  "original scenario.")

    # One feedback per scenario and task (or one general feedback without a task).
    title_for_check = task_info["title"] if task_info else None
    duplicate = db.query(Feedback).filter(Feedback.scenario_id == scenario.id,
                                          Feedback.task_title.is_(None) if title_for_check is None
                                          else Feedback.task_title == title_for_check).first()
    if duplicate:
        about = f"'{task_info['title']}'" if task_info else "this recommendation"
        raise FeedbackError(f"Feedback about {about} in this scenario was already recorded (feedback #{duplicate.id}). "
                            "Re-run the scenario to give feedback on the new result.", 409)

    title = task_info["title"] if task_info else None
    estimated = task_info["estimated_hours"] if task_info else None
    reading = interpret(payload, estimated, title)
    reading["notes"] = task_notes + reading["notes"]
    specs = reading["specs"]
    # Phase 6 permission gate: paused learning / history OFF -> the feedback is stored, the Twin is not changed.
    learning_allowed, blocked_reason = permission_gate.can_learn(permission_gate.get_or_create(db, payload.user_id))
    if specs and not learning_allowed:
        reading["notes"].insert(0, blocked_reason + " Your feedback and outcome were stored, but no observation was "
                                "created from them.")
        specs = []
    relevant = [label for label, t in summary.get("twin", {}).items() if t.get("source") in ("twin", "fallback")]

    try:
        feedback = Feedback(
            user_id=payload.user_id, scenario_id=scenario.id, recommended_plan_id=scenario.recommended_plan_id,
            task_id=linked_task_id, task_title=title, estimated_hours=estimated, rating=payload.rating,
            reasons=payload.reasons, actual_hours=payload.actual_hours, completed=payload.completed,
            deadline_met=payload.deadline_met, hours_late=payload.hours_late, notes=payload.notes,
            relevant_traits=relevant, interpretation={},
        )
        db.add(feedback)
        db.flush()  # gives feedback.id

        created, changes, snapshot = [], [], None
        if specs:
            traits_now = pattern_analyzer.get_traits(db, payload.user_id)
            before = _snapshot(traits_now)
            analyzed = traits_now[0].details.get("observations_in_twin", 0) if traits_now else 0
            total = db.query(BehaviorObservation).filter(BehaviorObservation.user_id == payload.user_id).count()
            pending = max(0, total - analyzed)

            now = utc_now()
            for spec in specs:
                obs = BehaviorObservation(
                    user_id=payload.user_id, task_id=linked_task_id,
                    observation_type=spec["type"], observed_value=spec["value"],
                    context={**spec["context"], "feedback_id": feedback.id, "scenario_id": scenario.id},
                    source="feedback", created_at=now,
                )
                db.add(obs)
                db.flush()
                created.append({"observation_id": obs.id, "observation_type": spec["type"],
                                "observed_value": spec["value"], "description": spec["text"]})

            after = _snapshot(pattern_analyzer.analyze_user(db, payload.user_id, commit=False))
            changes = diff(before, after, specs, pending)
            snapshot = TwinSnapshot(user_id=payload.user_id, feedback_id=feedback.id,
                                    reason="; ".join(s["text"] for s in specs),
                                    traits_before=before, traits_after=after, changes=changes)
            db.add(snapshot)

        significant = [c for c in changes if c["significant"]]
        if not learning_allowed and reading["specs"]:
            message = "Your feedback has been recorded. " + blocked_reason
        elif significant:
            message = "Your feedback has been recorded. Your Twin learned from this feedback."
        else:
            message = ("Your feedback has been recorded. No significant trait changes were detected - there is not "
                       "enough new behavioral evidence to meaningfully change a trait yet.")
        feedback.interpretation = {"evidence_found": bool(specs), "observations": created, "notes": reading["notes"],
                                   "note_category": reading["note_category"], "understood_by": reading["understood_by"]}
        db.commit()
    except Exception:
        db.rollback()  # nothing is half-saved
        raise

    steps = [
        {"step": "record", "title": "Feedback recorded", "detail": f"Feedback #{feedback.id} for scenario #{scenario.id}"},
        {"step": "interpret", "title": "Feedback interpreted",
         "detail": f"{len(created)} behavioral observation(s) found" if created else "No measurable behavioral evidence"},
    ]
    if created:
        steps += [
            {"step": "observe", "title": "Observations stored",
             "detail": ", ".join(f"{c['observation_type']} = {c['observed_value']:g}" for c in created)},
            {"step": "update", "title": "Twin updated",
             "detail": f"Pattern Analyzer: new = old + {ALPHA} x (observed - old); {len(changes)} trait(s) changed"},
            {"step": "diff", "title": "Twin Diff saved", "detail": f"Snapshot #{snapshot.id} (before and after)"},
        ]
    return {
        "feedback_id": feedback.id, "scenario_id": scenario.id, "recorded": True, "updated": bool(significant),
        "message": message, "interpretation": feedback.interpretation, "changes": changes,
        "snapshot_id": snapshot.id if snapshot else None, "learning_steps": steps,
        "learning_blocked": None if learning_allowed else blocked_reason,
    }
