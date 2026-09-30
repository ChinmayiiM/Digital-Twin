"""Synthetic demo observations for the demo user 'Alex'.

Nothing here runs automatically. A developer/judge triggers it with POST /api/demo/seed/{user_id}.
Every row is stored with source = "demo" and context.synthetic = true, so it can always be told
apart from real data (and removed again with DELETE /api/demo/seed/{user_id}).
The rows are ordinary observations: the Pattern Analyzer turns them into traits like any other data.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import BehaviorObservation
from app.services.pattern_analyzer import utc_now

_SYNTH = {"synthetic": True}


def _demo_rows() -> list:
    """(observation_type, observed_value, context) tuples."""
    rows = []

    # Productivity by time of day (0..1)
    for value in (0.78, 0.82, 0.80, 0.79, 0.81):
        rows.append(("working_time", value, {"time_period": "morning", **_SYNTH}))
    for value in (0.63, 0.67, 0.65, 0.66):
        rows.append(("working_time", value, {"time_period": "afternoon", **_SYNTH}))
    for value in (0.53, 0.57, 0.55, 0.56):
        rows.append(("working_time", value, {"time_period": "evening", **_SYNTH}))

    # Task estimation: (estimated, actual)
    for estimated, actual in ((2, 3), (4, 5), (3, 4), (5, 7)):
        rows.append(("task_estimation", float(actual), {"estimated_hours": float(estimated), **_SYNTH}))

    # Focus sessions (minutes)
    for minutes in (60, 75, 90, 70):
        rows.append(("focus_session", float(minutes), dict(_SYNTH)))

    # Task ordering: Alex usually finishes the SMALLER task first, even when a bigger one
    # has higher priority and an earlier deadline. The 5th choice is an exception.
    now = datetime.now().replace(microsecond=0)
    soon, later = (now + timedelta(days=1)).isoformat(), (now + timedelta(days=5)).isoformat()
    for small_hours in (1.5, 2.0, 1.0, 2.5):
        rows.append((
            "task_order", 1.0,
            {
                "chosen": {"estimated_hours": small_hours, "priority": "low", "deadline": later},
                "remaining": [
                    {"estimated_hours": 6, "priority": "high", "deadline": soon},
                    {"estimated_hours": 8, "priority": "high", "deadline": soon},
                ],
                **_SYNTH,
            },
        ))
    rows.append((
        "task_order", 1.0,
        {
            "chosen": {"estimated_hours": 6, "priority": "high", "deadline": soon},
            "remaining": [{"estimated_hours": 2, "priority": "low", "deadline": later}],
            **_SYNTH,
        },
    ))

    # Delays: hours after the deadline (0 = on time)
    for hours_late in (0, 4, 10, 0, 8):
        rows.append(("delay", float(hours_late), dict(_SYNTH)))

    return rows


def demo_exists(db: Session, user_id: int) -> bool:
    return (
        db.query(BehaviorObservation)
        .filter(BehaviorObservation.user_id == user_id, BehaviorObservation.source == "demo")
        .first()
        is not None
    )


def seed_demo_observations(db: Session, user_id: int) -> int:
    rows = _demo_rows()
    start = utc_now() - timedelta(hours=6 * len(rows))  # spread over the last few days
    for i, (kind, value, context) in enumerate(rows):
        db.add(BehaviorObservation(
            user_id=user_id,
            observation_type=kind,
            observed_value=value,
            context=context,
            source="demo",
            created_at=start + timedelta(hours=6 * i),
        ))
    db.commit()
    return len(rows)


def clear_demo_observations(db: Session, user_id: int) -> int:
    count = (
        db.query(BehaviorObservation)
        .filter(BehaviorObservation.user_id == user_id, BehaviorObservation.source == "demo")
        .delete(synchronize_session=False)
    )
    db.commit()
    return count
