"""Step 2 - PLAN: turn the understood question into 2-3 concrete alternative plans.

The plans are built from the user's REAL tasks (never random):

    Plan A  <focus task> first      - what the user proposed: the whole first day on the focus task
    Plan B  Balanced                - first day split in half, nearest deadline first
    Plan C  <deferred task> first   - the opposite order: finish the deferred task, then the focus task

A plan only decides the FIRST simulated day (the day the question is about). On every later day the
simulator uses the same neutral rule for all plans: earliest deadline first. So differences between
plans come only from the decision the user is asking about.

A day plan is a list of "segments":  {"task_id": 3, "hours": None}  = work on task 3 until it is done
                                     {"task_id": 3, "hours": 3.0}   = work on task 3 for at most 3 hours
When all segments are finished early, the remaining time goes to other tasks (earliest deadline first).
"""
from datetime import timedelta
from typing import List

from app.services.simulation_config import MAX_HORIZON_DAYS


def simulation_tasks(ctx: dict, intent: dict) -> list:
    """Tasks that compete for time in the simulation window: the focus + deferred tasks plus every other
    open task with a deadline inside the window."""
    start = intent["start_date"]
    last_allowed = start + timedelta(days=MAX_HORIZON_DAYS - 1)
    chosen = {intent["focus_task_id"], *intent["deferred_task_ids"]}
    tasks = [
        t for t in ctx["open_tasks"]
        if t.id in chosen or (t.deadline is not None and start <= t.deadline.date() <= last_allowed)
    ]
    return sorted(tasks, key=lambda t: (t.deadline, t.id))


def simulation_days(tasks: list, start_date) -> list:
    last = max(t.deadline.date() for t in tasks)
    count = max(1, min(MAX_HORIZON_DAYS, (last - start_date).days + 1))
    return [start_date + timedelta(days=i) for i in range(count)]


def build_plans(ctx: dict, intent: dict, tasks: list) -> List[dict]:
    by_id = {t.id: t for t in tasks}
    focus = by_id[intent["focus_task_id"]]
    deferred = by_id[intent["deferred_task_ids"][0]]  # the main task being postponed
    day_word = "today" if intent["time_horizon"] == "today" else "tomorrow"
    hours = ctx["available_hours"]
    half = round(hours / 2, 2)
    earlier, later = sorted([focus, deferred], key=lambda t: (t.deadline, t.id))

    return [
        {
            "id": "A", "key": "focus_first", "is_user_proposal": True,
            "name": f"{focus.title} first",
            "description": (f"Spend {day_word} ({hours:g} h) only on {focus.title} and postpone {deferred.title}. "
                            "From the next day on, work on whatever is due first."),
            "first_day": [{"task_id": focus.id, "hours": None}],
        },
        {
            "id": "B", "key": "balanced", "is_user_proposal": False,
            "name": "Balanced split",
            "description": (f"Split {day_word}: about {half:g} h on {earlier.title} (due first), then "
                            f"{later.title}. From the next day on, work on whatever is due first."),
            "first_day": [{"task_id": earlier.id, "hours": half}, {"task_id": later.id, "hours": None}],
        },
        {
            "id": "C", "key": "deferred_first", "is_user_proposal": False,
            "name": f"{deferred.title} first",
            "description": (f"Work on {deferred.title} {day_word} until it is finished, then use the remaining "
                            f"time for {focus.title}. From the next day on, work on whatever is due first."),
            "first_day": [{"task_id": deferred.id, "hours": None}, {"task_id": focus.id, "hours": None}],
        },
    ]
