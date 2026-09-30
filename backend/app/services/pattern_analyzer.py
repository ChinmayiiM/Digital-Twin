"""Pattern Analyzer: behavioral observations  ->  Twin traits (value + confidence + evidence).

Everything here is plain Python arithmetic. No LLM, no ML library.

How a trait value is learned (same idea for every numeric trait):
    new_value = old_value + ALPHA * (observed_value - old_value)
The first observation starts the value; every later observation nudges it by ALPHA (default 0.2),
so recent behavior counts more than old behavior.

How confidence works:
    confidence = min(1.0, evidence_count / CONFIDENCE_FULL_AT)      # 1 obs -> 10%, 10+ obs -> 100%
It only says how much evidence TwinMate has, NOT statistical certainty.

If a trait has fewer than MIN_EVIDENCE observations, no value is reported at all
(trait_value stays NULL and the text says "Not enough evidence yet").

The analysis is a full rebuild: it re-reads all of the user's observations in time order,
so running it twice on the same data gives the same Twin.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import BehaviorObservation, TwinTrait
from app.models.twin_trait import TRAIT_ORDER

ALPHA = 0.2  # learning rate of the update formula
MIN_EVIDENCE = 3  # observations needed before a trait value is shown
CONFIDENCE_FULL_AT = 10  # observations needed for 100% confidence

NOT_ENOUGH = "Not enough evidence yet"
PERIODS = ("morning", "afternoon", "evening")
PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}
ORDER_TEXT = {
    "smaller_first": "Prefers smaller tasks first",
    "priority_first": "Prefers higher-priority tasks first",
    "deadline_first": "Prefers nearest-deadline tasks first",
}
ORDER_PHRASE = {
    "smaller_first": "the smaller task",
    "priority_first": "the higher-priority task",
    "deadline_first": "the task with the nearest deadline",
}


# --------------------------------------------------------------------------- helpers
def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ema(values: List[float], alpha: float = ALPHA) -> float:
    """Exponential moving average using new = old + alpha * (observed - old)."""
    current = values[0]
    for observed in values[1:]:
        current = current + alpha * (observed - current)
    return current


def confidence_for(evidence_count: int) -> float:
    return round(min(1.0, evidence_count / CONFIDENCE_FULL_AT), 4)


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" + ("" if n == 1 else "s")


def _not_enough(n: int, noun: str) -> dict:
    return {
        "trait_value": None,
        "display_value": NOT_ENOUGH,
        "sufficient_evidence": False,
        "evidence_count": n,
        "description": (
            f"Your Twin has limited evidence for this prediction. It has {_plural(n, 'observation')} "
            f"of {noun}; at least {MIN_EVIDENCE} are needed before a value is reported."
        ),
        "details": {"minimum_evidence": MIN_EVIDENCE},
    }


def _number(value) -> Optional[float]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _date(value) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(str(value).replace("Z", ""))
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- traits
def productivity_trait(period: str, observations: List[BehaviorObservation], alpha: float) -> dict:
    values = [o.observed_value for o in observations if (o.context or {}).get("time_period") == period]
    n = len(values)
    if n < MIN_EVIDENCE:
        return _not_enough(n, f"{period} productivity")

    value = round(ema(values, alpha), 4)
    mean = sum(values) / n
    return {
        "trait_value": value,
        "display_value": f"{round(value * 100)}%",
        "sufficient_evidence": True,
        "evidence_count": n,
        "description": (
            f"Based on {_plural(n, 'observation')} of your {period} work (simple average {mean * 100:.0f}%). "
            f"Newer observations carry more weight (alpha = {alpha}), so the current estimate is {value * 100:.0f}%."
        ),
        "details": {"alpha": alpha, "average": round(mean, 4), "lowest": min(values), "highest": max(values)},
    }


def estimation_trait(observations: List[BehaviorObservation], alpha: float) -> dict:
    ratios = []
    for o in observations:
        estimated = _number((o.context or {}).get("estimated_hours"))
        if estimated and estimated > 0:
            ratios.append(o.observed_value / estimated)  # actual / estimated
    n = len(ratios)
    if n < MIN_EVIDENCE:
        return _not_enough(n, "estimated vs. actual task time")

    ratio = round(ema(ratios, alpha), 4)
    longer = sum(r > 1.05 for r in ratios)
    shorter = sum(r < 0.95 for r in ratios)
    if ratio > 1.05:
        text = f"Usually takes {round((ratio - 1) * 100)}% longer than estimated"
    elif ratio < 0.95:
        text = f"Usually finishes {round((1 - ratio) * 100)}% faster than estimated"
    else:
        text = "Estimates are usually accurate (within 5%)"
    return {
        "trait_value": ratio,
        "display_value": text,
        "sufficient_evidence": True,
        "evidence_count": n,
        "description": (
            f"{_plural(n, 'completed task')} {'was' if n == 1 else 'were'} compared with the original estimates "
            f"(ratio = actual hours / estimated hours). Actual time was higher than estimated in {longer} of {n} "
            f"and lower in {shorter}. Weighted ratio: {ratio:.2f} (alpha = {alpha})."
        ),
        "details": {
            "alpha": alpha,
            "ratio": ratio,
            "average_ratio": round(sum(ratios) / n, 4),
            "longer_than_estimated": longer,
            "shorter_than_estimated": shorter,
        },
    }


def focus_trait(observations: List[BehaviorObservation], alpha: float) -> dict:
    minutes = [o.observed_value for o in observations]
    n = len(minutes)
    if n < MIN_EVIDENCE:
        return _not_enough(n, "focus sessions")

    value = round(ema(minutes, alpha), 1)
    return {
        "trait_value": value,
        "display_value": f"{round(value)} minutes",
        "sufficient_evidence": True,
        "evidence_count": n,
        "description": (
            f"Based on {_plural(n, 'focus session')} ranging from {min(minutes):.0f} to {max(minutes):.0f} minutes "
            f"(simple average {sum(minutes) / n:.0f}). Newer sessions carry more weight (alpha = {alpha})."
        ),
        "details": {
            "alpha": alpha,
            "average_minutes": round(sum(minutes) / n, 1),
            "shortest_minutes": min(minutes),
            "longest_minutes": max(minutes),
        },
    }


def _order_matches(context: dict) -> Dict[str, bool]:
    """For ONE 'which task did the user finish first?' observation, say which rules it is consistent with.
    A rule is only judged when the choice could actually tell it apart (e.g. the tasks differ in size)."""
    chosen = context.get("chosen") or {}
    remaining = [r for r in (context.get("remaining") or []) if isinstance(r, dict)]
    result: Dict[str, bool] = {}

    hours = _number(chosen.get("estimated_hours"))
    other_hours = [h for h in (_number(r.get("estimated_hours")) for r in remaining) if h is not None]
    if hours is not None and other_hours and any(h != hours for h in other_hours):
        result["smaller_first"] = hours <= min(other_hours)

    rank = PRIORITY_RANK.get(str(chosen.get("priority", "")).lower())
    other_ranks = [x for x in (PRIORITY_RANK.get(str(r.get("priority", "")).lower()) for r in remaining) if x]
    if rank and other_ranks and any(x != rank for x in other_ranks):
        result["priority_first"] = rank >= max(other_ranks)

    due = _date(chosen.get("deadline"))
    other_due = [d for d in (_date(r.get("deadline")) for r in remaining) if d]
    if due and other_due and any(d != due for d in other_due):
        result["deadline_first"] = due <= min(other_due)

    return result


def ordering_trait(observations: List[BehaviorObservation], alpha: float) -> dict:
    n = len(observations)
    if n < MIN_EVIDENCE:
        return _not_enough(n, "which task you finished first")

    tally = {rule: {"matches": 0, "applicable": 0} for rule in ORDER_TEXT}
    for o in observations:
        for rule, matched in _order_matches(o.context or {}).items():
            tally[rule]["applicable"] += 1
            tally[rule]["matches"] += int(matched)

    for stats in tally.values():
        stats["rate"] = round(stats["matches"] / stats["applicable"], 4) if stats["applicable"] else None

    usable = sorted(
        ((rule, s) for rule, s in tally.items() if s["applicable"] >= MIN_EVIDENCE),
        key=lambda item: item[1]["rate"],
        reverse=True,
    )
    if not usable:
        result = _not_enough(n, "task choices that show a clear order")
        result["evidence_count"] = n
        result["details"] = {"minimum_evidence": MIN_EVIDENCE, "rules": tally}
        return result

    best_rule, best = usable[0]
    runner_up = usable[1][1]["rate"] if len(usable) > 1 else 0.0
    breakdown = "; ".join(
        f"{ORDER_TEXT[r].replace('Prefers ', '').replace(' first', '')}: {s['matches']}/{s['applicable']}"
        for r, s in tally.items()
        if s["applicable"]
    )

    # A rule wins only if it fits at least 60% of the choices AND clearly beats the runner-up.
    if best["rate"] >= 0.6 and best["rate"] - runner_up >= 0.15:
        return {
            "trait_value": best["rate"],
            "display_value": ORDER_TEXT[best_rule],
            "sufficient_evidence": True,
            "evidence_count": n,
            "description": (
                f"In {best['matches']} of {best['applicable']} recorded choices you finished "
                f"{ORDER_PHRASE[best_rule]} first ({best['rate'] * 100:.0f}%). Matches per rule - {breakdown}."
            ),
            "details": {"preference": best_rule, "rules": tally},
        }
    return {
        "trait_value": None,
        "display_value": "No clear ordering pattern yet",
        "sufficient_evidence": True,
        "evidence_count": n,
        "description": (
            f"{_plural(n, 'task choice')} recorded, but no single rule clearly explains them. "
            f"Matches per rule - {breakdown}."
        ),
        "details": {"preference": None, "rules": tally},
    }


def procrastination_trait(observations: List[BehaviorObservation], alpha: float) -> dict:
    delays = [o.observed_value for o in observations]  # hours after the deadline (0 = on time)
    n = len(delays)
    if n < MIN_EVIDENCE:
        return _not_enough(n, "task delays")

    scores = [min(1.0, d / 24) for d in delays]  # a full day late scores 1.0
    value = round(ema(scores, alpha), 4)
    label = "Low" if value < 0.25 else "Moderate" if value < 0.6 else "High"
    late = [d for d in delays if d > 0]
    average_late = sum(late) / len(late) if late else 0.0
    return {
        "trait_value": value,
        "display_value": label,
        "sufficient_evidence": True,
        "evidence_count": n,
        "description": (
            f"Of {_plural(n, 'tracked task')}, {len(late)} finished after the deadline"
            + (f" (on average {average_late:.1f} hours late)" if late else "")
            + f" and {n - len(late)} on time. Delay score {value:.2f} (Low < 0.25, Moderate < 0.60, High otherwise). "
            "This is only a task-delay metric, not a judgement about you."
        ),
        "details": {
            "alpha": alpha,
            "delay_score": value,
            "delayed_tasks": len(late),
            "on_time_tasks": n - len(late),
            "average_delay_hours": round(average_late, 2),
        },
    }


# --------------------------------------------------------------------------- main entry points
def compute_traits(observations: List[BehaviorObservation], alpha: float = ALPHA) -> Dict[str, dict]:
    """Pure calculation (no database): observations in time order -> {trait_name: result}."""
    by_type = lambda kind: [o for o in observations if o.observation_type == kind]  # noqa: E731

    working = by_type("working_time")
    results = {f"productivity_{p}": productivity_trait(p, working, alpha) for p in PERIODS}
    results["task_estimation"] = estimation_trait(by_type("task_estimation"), alpha)
    results["focus_capacity"] = focus_trait(by_type("focus_session"), alpha)
    results["task_ordering"] = ordering_trait(by_type("task_order"), alpha)
    results["procrastination"] = procrastination_trait(by_type("delay"), alpha)

    for result in results.values():
        result["confidence"] = confidence_for(result["evidence_count"])
    return results


def analyze_user(db: Session, user_id: int, alpha: float = ALPHA, commit: bool = True) -> List[TwinTrait]:
    """Rebuild and save all Twin traits for ONE user (every query is filtered by user_id).

    commit=False lets a caller (Phase 5 feedback) run this inside its own transaction, so feedback,
    observations, traits and the snapshot are saved together or not at all."""
    observations = (
        db.query(BehaviorObservation)
        .filter(BehaviorObservation.user_id == user_id)
        .order_by(BehaviorObservation.created_at, BehaviorObservation.id)
        .all()
    )
    results = compute_traits(observations, alpha)
    now = utc_now()

    existing = {t.trait_name: t for t in db.query(TwinTrait).filter(TwinTrait.user_id == user_id).all()}
    for name in TRAIT_ORDER:
        result = results[name]
        trait = existing.get(name)
        if trait is None:
            trait = TwinTrait(user_id=user_id, trait_name=name)
            db.add(trait)
        trait.trait_value = result["trait_value"]
        trait.display_value = result["display_value"]
        trait.confidence = result["confidence"]
        trait.evidence_count = result["evidence_count"]
        trait.sufficient_evidence = result["sufficient_evidence"]
        trait.description = result["description"]
        trait.details = {**result["details"], "observations_in_twin": len(observations)}
        trait.last_updated = now
    if commit:
        db.commit()
    else:
        db.flush()

    return get_traits(db, user_id)


def get_traits(db: Session, user_id: int) -> List[TwinTrait]:
    rows = db.query(TwinTrait).filter(TwinTrait.user_id == user_id).all()
    return sorted(rows, key=lambda t: TRAIT_ORDER.index(t.trait_name) if t.trait_name in TRAIT_ORDER else 99)
