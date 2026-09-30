"""Step 4 - COMPARE the simulated plans side by side.

It only re-arranges numbers the simulator already calculated into table rows, and writes factual
trade-off notes per plan. It never marks a plan as "best" or "winner" - that is the recommender's job,
and the recommendation is shown separately.
"""
from typing import Dict, List

from app.services import simulation_config as cfg


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def compare(plans: List[dict], ctx: dict, day_word: str) -> dict:
    ids = [p["id"] for p in plans]
    rows = []

    def row(metric, kind, raw: Dict[str, float], text: Dict[str, str]):
        rows.append({"metric": metric, "kind": kind, "raw": raw, "values": text})

    task_list = plans[0]["tasks"]
    for k, task in enumerate(task_list):
        raw = {p["id"]: p["tasks"][k]["expected_progress"] for p in plans}
        row(f"{task['title']} - progress by deadline", "percent", raw, {i: _pct(v) for i, v in raw.items()})
        raw = {p["id"]: p["tasks"][k]["on_time_probability"] for p in plans}
        row(f"{task['title']} - chance to finish on time", "percent", raw, {i: _pct(v) for i, v in raw.items()})

    raw = {p["id"]: p["max_deadline_risk"] for p in plans}
    row("Deadline risk (worst task)", "label", raw, {p["id"]: f"{p['risk_label']} ({_pct(p['max_deadline_risk'])})" for p in plans})

    raw = {p["id"]: p["overall_expected"] for p in plans}
    row("Expected overall progress", "percent", raw, {i: _pct(v) for i, v in raw.items()})
    row("Likely range (10th-90th percentile)", "range", {p["id"]: p["overall_high"] - p["overall_low"] for p in plans},
        {p["id"]: f"{_pct(p['overall_low'])} - {_pct(p['overall_high'])}" for p in plans})

    raw = {p["id"]: p["workload_ratio"] for p in plans}
    row("Workload (required / capacity)", "ratio", raw, {p["id"]: f"{p['workload_label']} ({p['workload_ratio']:.2f})" for p in plans})

    raw = {p["id"]: p["capacity_usage"] for p in plans}
    row("Capacity usage", "percent", raw, {i: _pct(v) for i, v in raw.items()})

    raw = {p["id"]: float(p["first_day_switches"]) for p in plans}
    row(f"Task switches {day_word}", "ratio", raw, {i: str(int(v)) for i, v in raw.items()})

    return {
        "plan_ids": ids,
        "plan_names": {p["id"]: p["name"] for p in plans},
        "rows": rows,
        "trade_offs": {p["id"]: _trade_offs(p, plans, ctx, day_word) for p in plans},
    }


def _trade_offs(plan: dict, plans: List[dict], ctx: dict, day_word: str) -> List[str]:
    notes = []
    others = [p for p in plans if p["id"] != plan["id"]]
    for k, task in enumerate(plan["tasks"]):
        mine = task["on_time_probability"]
        best_other = max(p["tasks"][k]["on_time_probability"] for p in others)
        if mine - best_other >= 0.05:
            notes.append(f"Highest chance among the plans to finish {task['title']} on time ({_pct(mine)}).")
        if task["deadline_risk"] >= cfg.RISK_HIGH:
            notes.append(f"{task['title']}: {_pct(task['deadline_risk'])} chance of missing the deadline.")

    # Unused time only matters if it happens BEFORE the deadline of a task that is at risk.
    for task in plan["tasks"]:
        if task["deadline_risk"] >= cfg.RISK_HIGH:
            unused = sum(day["idle_hours"] for day in plan["schedule"] if day["date"] <= task["deadline"].date())
            if unused >= 0.5:
                notes.append(f"Leaves about {unused:.1f} h unused before {task['title']}'s deadline.")

    if plan["first_day_switches"] == 0:
        notes.append(f"No task switching {day_word}.")
    else:
        minutes = plan["first_day_switches"] * cfg.SWITCH_COST * ctx["available_hours"] * 60
        notes.append(f"{plan['first_day_switches']} task switch(es) {day_word} (about {minutes:.0f} min of refocusing).")
    return notes
