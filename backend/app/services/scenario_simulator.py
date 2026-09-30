"""Step 3 - SIMULATE each plan with the user's Digital Twin. Plain Python + NumPy, no LLM.

HOW ONE SIMULATED DAY WORKS (hour by hour)
-------------------------------------------
    required_hours  = task.estimated_hours x estimation_ratio          (Twin: "takes 42% longer")
    work done in a slot = slot_hours x productivity_factor x fatigue_factor
        productivity_factor = productivity_of_this_period / your_average_productivity   (Twin)
        fatigue_factor      = max(0.70, 1 - fatigue_rate x hours_over_4)
    switching task      = loses SWITCH_COST x available_hours of the day (no progress)
    procrastination     = with probability = Twin delay score, 1 hour of the day is lost

Why productivity is RELATIVE to your own average: the estimation ratio was measured from your real
(average) working speed. Multiplying by raw productivity as well would count slowness twice. So an
hour in your best period counts a bit more than an average hour, an hour in your weakest period less.

The day's hours are spent in the order of your preferred working time
(Morning -> first 4 h morning, next 4 h afternoon, rest evening).

Work only counts for a task while its deadline has not passed (a day counts if it is on or before the
deadline date - we assume the work happens before the deadline time on that day).

MONTE CARLO
-----------
The same day model runs N_SIMULATIONS times. Each run draws its own values around the Twin's learned
values (spread = measured variation of your observations, wider when evidence is limited):
    estimation ratio per task, productivity per period per day, fatigue rate, lost time, availability noise.
All plans use the SAME random draws, so differences between plans come only from the plans themselves.
"""
import math
from typing import Dict, List

import numpy as np

from app.services import simulation_config as cfg

PERIODS = ("morning", "afternoon", "evening")


# ------------------------------------------------------------------ small model pieces
def period_for(clock: float, ctx: dict) -> str:
    index = min(int(clock // cfg.PERIOD_BLOCK_HOURS), 2)
    return ctx["period_order"][index]


def work_rate(clock: float, productivity_today: Dict[str, float], fatigue_rate: float, ctx: dict) -> float:
    """How many 'required hours' of progress one clock hour produces at this moment of the day."""
    period = period_for(clock, ctx)
    factor = productivity_today[period] / ctx["reference_productivity"]
    factor = min(cfg.PRODUCTIVITY_FACTOR_MAX, max(cfg.PRODUCTIVITY_FACTOR_MIN, factor))
    hours_over = int(clock) - cfg.FATIGUE_THRESHOLD_HOURS + 1
    fatigue = max(cfg.FATIGUE_FLOOR, 1.0 - fatigue_rate * hours_over) if hours_over > 0 else 1.0
    return factor * fatigue


def _next_task(segments, used, eligible, tasks_by_deadline):
    """Which task to work on now: the plan's segments first, otherwise earliest deadline first."""
    for i, seg in enumerate(segments):
        if seg["task_id"] in eligible and (seg["hours"] is None or used[i] < seg["hours"] - 1e-9):
            return i, seg["task_id"]
    for t in tasks_by_deadline:
        if t.id in eligible:
            return None, t.id
    return None, None


# ------------------------------------------------------------------ one run of one plan
def run_plan(plan: dict, tasks: list, days: list, ctx: dict, sample: dict, record: bool = False) -> dict:
    hours_per_day = ctx["available_hours"]
    required = {t.id: t.estimated_hours * sample["ratio"][t.id] for t in tasks}
    remaining = dict(required)
    progress_before_deadline = {t.id: 0.0 for t in tasks}
    on_time = {t.id: False for t in tasks}
    clock_hours_for_task = {t.id: 0.0 for t in tasks}
    worked, first_day_switches, switch_hours_total = 0.0, 0, 0.0
    schedule = []

    for d, day in enumerate(days):
        available = min(24.0, max(0.0, hours_per_day + sample["noise"][d] - sample["lost"][d]))
        eligible = {t.id for t in tasks if day <= t.deadline.date() and remaining[t.id] > 1e-9}
        segments = plan["first_day"] if d == 0 else []
        used = [0.0] * len(segments)
        clock, current, switch_hours = 0.0, None, 0.0
        blocks: Dict[int, float] = {}

        while clock < available - 1e-9:
            seg_index, task_id = _next_task(segments, used, eligible, tasks)
            if task_id is None:
                break  # nothing left that can still meet its deadline -> idle
            if current is not None and task_id != current:
                loss = min(cfg.SWITCH_COST * hours_per_day, available - clock)
                clock += loss
                switch_hours += loss
                first_day_switches += int(d == 0)
                current = task_id
                continue
            current = task_id

            slot_end = min(available, math.floor(clock + 1e-9) + 1.0)  # at most to the next full hour
            if seg_index is not None and segments[seg_index]["hours"] is not None:
                slot_end = min(slot_end, clock + segments[seg_index]["hours"] - used[seg_index])
            dt = slot_end - clock
            rate = work_rate(clock, sample["prod"][d], sample["fatigue_rate"], ctx)
            finished = remaining[task_id] <= dt * rate
            if finished:
                dt = remaining[task_id] / rate

            done = dt * rate
            remaining[task_id] = 0.0 if finished else remaining[task_id] - done
            progress_before_deadline[task_id] += done
            clock_hours_for_task[task_id] += dt
            blocks[task_id] = blocks.get(task_id, 0.0) + dt
            clock += dt
            worked += dt
            if seg_index is not None:
                used[seg_index] += dt
            if finished:
                on_time[task_id] = True
                eligible.discard(task_id)

        switch_hours_total += switch_hours
        if record:
            schedule.append({"date": day, "blocks": blocks, "idle_hours": max(0.0, available - clock),
                             "switch_hours": switch_hours, "available": available})

    return {
        "required": required,
        "progress": {tid: min(1.0, progress_before_deadline[tid] / required[tid]) for tid in required},
        "on_time": on_time,
        "clock_hours_for_task": clock_hours_for_task,
        "worked": worked,
        "first_day_switches": first_day_switches,
        "switch_hours": switch_hours_total,
        "schedule": schedule,
    }


# ------------------------------------------------------------------ samples
def typical_sample(tasks: list, days: list, ctx: dict) -> dict:
    """Every uncertain value at its learned (mean) value - used for the 'typical day' schedule."""
    prod = {p: ctx["productivity"][p]["mean"] for p in PERIODS}
    expected_loss = ctx["procrastination"]["score"] * cfg.PROCRASTINATION_LOSS_HOURS
    return {
        "ratio": {t.id: ctx["estimation"]["ratio"] for t in tasks},
        "prod": [prod for _ in days],
        "fatigue_rate": cfg.FATIGUE_RATE,
        "lost": [expected_loss for _ in days],
        "noise": [0.0 for _ in days],
    }


def monte_carlo_samples(tasks: list, days: list, ctx: dict, n: int, seed: int) -> List[dict]:
    rng = np.random.default_rng(seed)
    n_days = len(days)
    est = ctx["estimation"]
    ratios = {t.id: np.clip(rng.normal(est["ratio"], est["sd"], n), 0.5, 3.0) for t in sorted(tasks, key=lambda t: t.id)}
    prod = {p: np.clip(rng.normal(ctx["productivity"][p]["mean"], ctx["productivity"][p]["sd"], (n, n_days)), 0.2, 1.0)
            for p in PERIODS}
    fatigue = rng.uniform(*cfg.FATIGUE_RATE_RANGE, n)
    lost = (rng.random((n, n_days)) < ctx["procrastination"]["score"]) * cfg.PROCRASTINATION_LOSS_HOURS
    noise = rng.normal(0.0, cfg.AVAILABILITY_NOISE_SD, (n, n_days))

    return [
        {
            "ratio": {tid: float(r[i]) for tid, r in ratios.items()},
            "prod": [{p: float(prod[p][i, d]) for p in PERIODS} for d in range(n_days)],
            "fatigue_rate": float(fatigue[i]),
            "lost": lost[i].tolist(),
            "noise": noise[i].tolist(),
        }
        for i in range(n)
    ]


# ------------------------------------------------------------------ capacity helpers
def effective_capacity(days: list, ctx: dict, sample: dict) -> List[float]:
    """Effective hours (in 'required hour' units) each day could deliver if fully used - typical values."""
    result = []
    for d in range(len(days)):
        available = max(0.0, ctx["available_hours"] + sample["noise"][d] - sample["lost"][d])
        total, clock = 0.0, 0.0
        while clock < available - 1e-9:
            dt = min(available, math.floor(clock + 1e-9) + 1.0) - clock
            total += dt * work_rate(clock, sample["prod"][d], sample["fatigue_rate"], ctx)
            clock += dt
        result.append(total)
    return result


def deadline_windows(tasks: list, days: list, ctx: dict) -> List[dict]:
    """For every deadline: work due by then vs. effective capacity until then (same for every plan)."""
    typical = typical_sample(tasks, days, ctx)
    capacity = effective_capacity(days, ctx, typical)
    windows = []
    for t in tasks:
        last = t.deadline.date()
        cap = sum(c for day, c in zip(days, capacity) if day <= last)
        due = sum(x.estimated_hours * ctx["estimation"]["ratio"] for x in tasks if x.deadline <= t.deadline)
        windows.append({"task_id": t.id, "task_title": t.title, "deadline": t.deadline,
                        "required_hours": round(due, 2), "effective_capacity": round(cap, 2),
                        "ratio": round(due / cap, 2) if cap > 0 else None})
    return windows


# ------------------------------------------------------------------ main entry point
def simulate_plans(plans: List[dict], tasks: list, days: list, ctx: dict,
                   n: int = cfg.N_SIMULATIONS, seed: int = cfg.RANDOM_SEED) -> List[dict]:
    weights = np.array([cfg.PRIORITY_WEIGHT.get(t.priority, 1.0) for t in tasks])
    typical = typical_sample(tasks, days, ctx)
    capacity_total = sum(effective_capacity(days, ctx, typical))
    nominal_hours = ctx["available_hours"] * len(days)
    samples = monte_carlo_samples(tasks, days, ctx, n, seed)
    titles = {t.id: t.title for t in tasks}

    results = []
    for plan in plans:
        base = run_plan(plan, tasks, days, ctx, typical, record=True)

        progress = np.zeros((n, len(tasks)))
        on_time = np.zeros((n, len(tasks)))
        worked = np.zeros(n)
        for i, sample in enumerate(samples):
            run = run_plan(plan, tasks, days, ctx, sample)
            progress[i] = [run["progress"][t.id] for t in tasks]
            on_time[i] = [run["on_time"][t.id] for t in tasks]
            worked[i] = run["worked"]

        overall = progress @ weights / weights.sum()  # priority-weighted progress of each run
        task_rows = []
        for k, t in enumerate(tasks):
            p_on_time = float(on_time[:, k].mean())
            risk = 1.0 - p_on_time
            task_rows.append({
                "task_id": t.id, "title": t.title, "priority": t.priority, "deadline": t.deadline,
                "estimated_hours": t.estimated_hours,
                "adjusted_required_hours": round(base["required"][t.id], 2),
                "expected_progress": round(float(progress[:, k].mean()), 4),
                "progress_low": round(float(np.percentile(progress[:, k], 10)), 4),
                "progress_high": round(float(np.percentile(progress[:, k], 90)), 4),
                "on_time_probability": round(p_on_time, 4),
                "deadline_risk": round(risk, 4),
                "risk_label": cfg.risk_label(risk),
                "hours_before_deadline": round(base["clock_hours_for_task"][t.id], 2),
            })

        required_total = sum(base["required"].values())
        plan_capacity = max(1e-6, capacity_total - base["switch_hours"])
        workload = required_total / plan_capacity
        max_risk = max(r["deadline_risk"] for r in task_rows)

        results.append({
            "id": plan["id"], "key": plan["key"], "name": plan["name"], "description": plan["description"],
            "is_user_proposal": plan["is_user_proposal"],
            "first_day_switches": base["first_day_switches"],
            "tasks": task_rows,
            "overall_expected": round(float(overall.mean()), 4),
            "overall_low": round(float(np.percentile(overall, 10)), 4),
            "overall_high": round(float(np.percentile(overall, 90)), 4),
            "max_deadline_risk": round(max_risk, 4),
            "risk_label": cfg.risk_label(max_risk),
            "workload_ratio": round(workload, 2),
            "workload_label": cfg.workload_label(workload),
            "capacity_usage": round(float(worked.mean()) / nominal_hours, 4) if nominal_hours else 0.0,
            "schedule": [
                {
                    "date": day["date"],
                    "label": day["date"].strftime("%a, %b %d").replace(" 0", " "),
                    "blocks": [{"task_id": tid, "task_title": titles[tid], "hours": round(h, 2)}
                               for tid, h in day["blocks"].items() if h > 0.005],
                    "idle_hours": round(day["idle_hours"], 2),
                    "switch_hours": round(day["switch_hours"], 2),
                }
                for day in base["schedule"]
            ],
        })
    return results
