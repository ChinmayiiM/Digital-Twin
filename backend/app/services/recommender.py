"""Step 5 - DECIDE: pick a plan with an explicit, documented score (no LLM involved).

    score = 0.4 x progress        (priority-weighted expected progress before each deadline)
          + 0.4 x on_time         (priority-weighted chance of finishing each task on time)
          - 0.3 x worst_risk      (highest deadline risk of any task in the plan)
          - 0.2 x max(0, workload - 1)
          + 0.03 if the plan starts the way the Twin's observed task-ordering habit says

If the two best scores are closer than 0.03, TwinMate does NOT force a recommendation.

This file also builds the transparency parts of the answer: the reasons (every sentence is filled
with calculated numbers), trade-offs, the "Twin data used" list and the prediction confidence.
"""
import math
from typing import List, Optional

from app.services import simulation_config as cfg

FORMULA = ("score = 0.4 x progress + 0.4 x on-time chance - 0.3 x worst deadline risk "
           "- 0.2 x max(0, workload - 1) + 0.03 habit bonus")
PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _deadline_text(dt) -> str:
    return dt.strftime("%a, %b %d, %I:%M %p").replace(" 0", " ")


# ------------------------------------------------------------------ habit (task ordering trait)
def _habit_fits(plan: dict, pair_ids: set, tasks_by_id: dict, ctx: dict) -> Optional[bool]:
    """True/False if the plan's FIRST task fits the observed ordering habit (compared with the other task of
    the decision). None if the habit is unknown or cannot tell the two tasks apart."""
    ordering = ctx.get("ordering")
    if not ordering:
        return None
    first = tasks_by_id[plan["first_day"][0]["task_id"]]
    others = [tasks_by_id[i] for i in sorted(pair_ids) if i != first.id]
    if not others:
        return None
    other = others[0]
    rule = ordering["preference"]
    if rule == "smaller_first" and first.estimated_hours != other.estimated_hours:
        return first.estimated_hours < other.estimated_hours
    if rule == "priority_first" and first.priority != other.priority:
        return PRIORITY_RANK.get(first.priority, 0) > PRIORITY_RANK.get(other.priority, 0)
    if rule == "deadline_first" and first.deadline != other.deadline:
        return first.deadline < other.deadline
    return None


# ------------------------------------------------------------------ scoring
def score_plans(results: List[dict], plans: List[dict], tasks: list, ctx: dict) -> List[dict]:
    tasks_by_id = {t.id: t for t in tasks}
    pair_ids = {s["task_id"] for p in plans for s in p["first_day"]}  # the two tasks of the decision
    scores = []
    for plan, res in zip(plans, results):
        weights = [cfg.PRIORITY_WEIGHT.get(t["priority"], 1.0) for t in res["tasks"]]
        on_time = sum(w * t["on_time_probability"] for w, t in zip(weights, res["tasks"])) / sum(weights)
        progress = res["overall_expected"]
        risk_penalty = cfg.W_RISK * res["max_deadline_risk"]
        overload_penalty = cfg.W_OVERLOAD * max(0.0, res["workload_ratio"] - 1.0)
        habit = _habit_fits(plan, pair_ids, tasks_by_id, ctx)
        habit_bonus = cfg.HABIT_BONUS if habit else 0.0
        total = cfg.W_PROGRESS * progress + cfg.W_ON_TIME * on_time - risk_penalty - overload_penalty + habit_bonus
        scores.append({"plan_id": res["id"], "progress": round(progress, 4), "on_time": round(on_time, 4),
                       "risk_penalty": round(risk_penalty, 4), "overload_penalty": round(overload_penalty, 4),
                       "habit_bonus": habit_bonus, "total": round(total, 4), "_habit": habit})
    return scores


def recommend(results: List[dict], plans: List[dict], tasks: list, ctx: dict, intent: dict,
              windows: List[dict]) -> dict:
    scores = score_plans(results, plans, tasks, ctx)
    ranked = sorted(scores, key=lambda s: s["total"], reverse=True)
    by_id = {r["id"]: r for r in results}
    proposed = next(r for r in results if r["is_user_proposal"])
    day_word = "today" if intent["time_horizon"] == "today" else "tomorrow"
    public_scores = [{k: v for k, v in s.items() if not k.startswith("_")} for s in scores]

    if ranked[0]["total"] - ranked[1]["total"] < cfg.NO_CLEAR_PREFERENCE_MARGIN:
        a, b = by_id[ranked[0]["plan_id"]], by_id[ranked[1]["plan_id"]]
        return {
            "recommended_plan_id": None, "recommended_plan_name": None, "no_clear_preference": True,
            "headline": "No clear preference",
            "reasons": [
                f"The simulated outcomes are very similar: Plan {a['id']} scores {ranked[0]['total']:.2f} and "
                f"Plan {b['id']} scores {ranked[1]['total']:.2f}.",
                "Your decision may depend on which goal you personally want to prioritize.",
            ],
            "trade_offs": [], "scores": public_scores, "formula": FORMULA,
        }

    best = by_id[ranked[0]["plan_id"]]
    best_score = ranked[0]
    reasons: List[str] = []
    trade_offs: List[str] = []

    # 1) the deadline that decides the most
    first_task = min(best["tasks"], key=lambda t: t["deadline"])
    k = best["tasks"].index(first_task)
    line = (f"{first_task['title']} is due first ({_deadline_text(first_task['deadline'])}). "
            f"Plan {best['id']} gives it a {_pct(first_task['on_time_probability'])} chance of being finished on time")
    if best["id"] != proposed["id"]:
        line += f", compared with {_pct(proposed['tasks'][k]['on_time_probability'])} in your proposed Plan {proposed['id']}"
    reasons.append(line + ".")

    # 2) estimation tendency (why the Twin matters)
    est = ctx["estimation"]
    window = next((w for w in windows if w["task_id"] == first_task["task_id"]), None)
    if est["info"]["source"] == "twin" and abs(est["ratio"] - 1) >= 0.05:
        direction = "longer" if est["ratio"] > 1 else "less time"
        amount = abs(round((est["ratio"] - 1) * 100))
        line = (f"Your Twin shows tasks usually take {amount}% {direction} than estimated, so {first_task['title']} "
                f"needs about {first_task['adjusted_required_hours']:.1f} h instead of {first_task['estimated_hours']:g} h")
        if window and window["ratio"] and window["ratio"] > 1:
            line += f" - more than the ≈{window['effective_capacity']:.1f} effective hours you have before its deadline"
        reasons.append(line + ".")

    # 3) productivity in the preferred period
    first_period = ctx["period_order"][0]
    prod = ctx["productivity"][first_period]
    first_block = best["schedule"][0]["blocks"][0]["task_title"] if best["schedule"][0]["blocks"] else None
    if prod["info"]["source"] == "twin" and first_block:
        reasons.append(
            f"Your day starts in your {first_period} period, where your observed productivity is {_pct(prod['mean'])} "
            f"(your average is {_pct(ctx['reference_productivity'])}); Plan {best['id']} puts {first_block} there.")
    elif prod["info"]["source"] == "not_permitted":
        reasons.append("Behavioral patterns are not used (permission off), so every time of day is treated the same.")
    elif prod["info"]["source"] != "twin":
        reasons.append("Productivity evidence is limited, so every time of day is treated the same in this simulation.")

    # 4) task switching
    min_switches = min(r["first_day_switches"] for r in results)
    if best["first_day_switches"] == 0:
        reasons.append(f"Focusing on one task {day_word} avoids task-switching overhead.")
    elif best["first_day_switches"] > min_switches:
        minutes = best["first_day_switches"] * cfg.SWITCH_COST * ctx["available_hours"] * 60
        trade_offs.append(f"It needs {best['first_day_switches']} task switch(es) {day_word} "
                          f"(about {minutes:.0f} minutes of refocusing).")

    # 5) habit
    if best_score["_habit"]:
        reasons.append(f"It matches your observed habit: {ctx['ordering']['info']['display_value'].lower()}.")

    # trade-offs: remaining risks + where another plan does better
    for t in best["tasks"]:
        if t["deadline_risk"] >= cfg.RISK_LOW:
            trade_offs.append(f"{t['title']} still has {t['risk_label'].lower()} deadline risk "
                              f"({_pct(t['deadline_risk'])} chance of missing it).")
    for other in results:
        if other["id"] == best["id"]:
            continue
        for j, t in enumerate(other["tasks"]):
            if t["expected_progress"] - best["tasks"][j]["expected_progress"] >= 0.05:
                trade_offs.append(f"Plan {other['id']} would reach more progress on {t['title']} by its deadline "
                                  f"({_pct(t['expected_progress'])} vs {_pct(best['tasks'][j]['expected_progress'])}).")

    return {
        "recommended_plan_id": best["id"],
        "recommended_plan_name": f"Plan {best['id']} - {best['name']}",
        "no_clear_preference": False,
        "headline": f"Plan {best['id']} - {best['name']}",
        "reasons": reasons, "trade_offs": trade_offs, "scores": public_scores, "formula": FORMULA,
    }


# ------------------------------------------------------------------ transparency
def periods_used(ctx: dict) -> List[str]:
    blocks = max(1, min(3, math.ceil(ctx["available_hours"] / cfg.PERIOD_BLOCK_HOURS)))
    return ctx["period_order"][:blocks]


def twin_data_used(ctx: dict) -> List[dict]:
    items = [
        {"label": "Available hours", "value": f"{ctx['available_hours']:g} hours/day", "source": "profile",
         "used_for": "daily capacity"},
        {"label": "Preferred working time", "value": ctx["preferred_working_time"], "source": "profile",
         "used_for": "the order in which the day's hours are spent"}
        if ctx["permissions"]["preferences"] else
        {"label": "Preferred working time", "value": "Not used - permission off", "source": "not_permitted",
         "used_for": "nothing (day order follows observed productivity instead)"},
    ]
    traits = [ctx["productivity"][p]["info"] for p in periods_used(ctx)]
    traits += [ctx["estimation"]["info"], ctx["procrastination"]["info"]]
    if ctx.get("ordering"):
        traits.append(ctx["ordering"]["info"])
    for info in traits:
        is_prod = info["label"].endswith("productivity")
        value = _pct(info["used_value"]) if is_prod and info["source"] == "twin" else info["display_value"]
        if info["source"] == "fallback":
            value = "Not enough evidence - neutral assumption"
        elif info["source"] == "not_permitted":
            value = "Not used"
        items.append({"label": info["label"], "value": value, "source": info["source"],
                      "confidence": info["confidence"], "evidence_count": info["evidence_count"],
                      "used_for": info["used_for"]})
    return items


def confidence_info(ctx: dict, result: dict) -> dict:
    infos = [ctx["productivity"][p]["info"] for p in periods_used(ctx)]
    infos += [ctx["estimation"]["info"], ctx["procrastination"]["info"]]
    confidences = [i["confidence"] if i["source"] == "twin" else 0.0 for i in infos]
    score = sum(confidences) / len(confidences)
    evidence = sum(i["evidence_count"] for i in infos if i["source"] == "twin")
    label = cfg.confidence_label(score)
    weak = [i for i in infos if i["source"] in ("fallback", "not_permitted")]
    limited = label == "Low" or bool(weak)

    if not ctx["permissions"]["behavior"]:
        message = ("Your Twin has limited evidence for this prediction: the Behavioral Patterns permission is off, "
                   "so no learned traits were used - only your tasks, schedule and neutral assumptions.")
    elif limited:
        names = ", ".join(i["label"].lower() for i in weak) or "several traits"
        message = ("Your Twin has limited evidence for this prediction. This simulation uses your available task, "
                   "schedule and preference data, but some behavioral traits are not yet well established "
                   f"({names}).")
    else:
        least = min(infos, key=lambda i: i["confidence"])
        message = (f"Your Twin has {evidence} relevant observations. Each trait reaches full confidence at 10 "
                   f"observations; the least established one here is {least['label'].lower()} "
                   f"({least['evidence_count']} observations, {_pct(least['confidence'])} confidence), "
                   "so treat the range as approximate.")
    return {"score": round(score, 4), "label": label, "evidence_count": evidence, "limited_evidence": limited,
            "message": message, "expected_outcome": result["overall_expected"],
            "outcome_low": result["overall_low"], "outcome_high": result["overall_high"]}


def data_used(ctx: dict, tasks: list) -> List[dict]:
    """Phase 6 'View data used': every category, whether it was permitted, and exactly what was used."""
    allowed = ctx["permissions"]

    def fmt(dt):
        return dt.strftime("%b %d, %I:%M %p").replace(" 0", " ")

    trait_items = []
    for info in [ctx["productivity"][p]["info"] for p in periods_used(ctx)] + \
            [ctx["estimation"]["info"], ctx["procrastination"]["info"]] + \
            ([ctx["ordering"]["info"]] if ctx.get("ordering") else []):
        if info["source"] == "twin":
            trait_items.append({"name": info["label"], "value": info["display_value"] if not info["label"].endswith(
                "productivity") else _pct(info["used_value"]),
                "detail": f"{info['evidence_count']} observations, {cfg.confidence_label(info['confidence'])} confidence"})
        elif info["source"] == "fallback":
            trait_items.append({"name": info["label"], "value": "Not enough evidence",
                                "detail": "a neutral value was used instead"})

    goal_titles = list(dict.fromkeys(t.goal.title for t in tasks if t.goal is not None))
    return [
        {"key": "timetable", "label": "Timetable & Available Hours", "permitted": allowed["timetable"],
         "used": allowed["timetable"],
         "items": [{"name": "Available hours", "value": f"{ctx['available_hours']:g} hours/day", "detail": "daily capacity"}]
         if ctx["available_hours"] else [], "note": ""},
        {"key": "tasks", "label": "Tasks & Deadlines", "permitted": allowed["tasks"], "used": allowed["tasks"],
         "items": [{"name": t.title, "value": f"{t.estimated_hours:g} h estimated",
                    "detail": f"deadline {fmt(t.deadline)}, {t.priority} priority"} for t in tasks], "note": ""},
        {"key": "goals", "label": "Goals", "permitted": allowed["goals"], "used": allowed["goals"] and bool(goal_titles),
         "items": [{"name": g, "value": "", "detail": "helps recognise tasks in your question"} for g in goal_titles]
         if allowed["goals"] else [],
         "note": "" if allowed["goals"] else "Not used - permission off."},
        {"key": "preferences", "label": "Preferences", "permitted": allowed["preferences"],
         "used": allowed["preferences"] and bool(ctx["preferred_working_time"]),
         "items": [{"name": "Preferred working time", "value": ctx["preferred_working_time"],
                    "detail": "order of the day's hours"}] if allowed["preferences"] and ctx["preferred_working_time"] else [],
         "note": "" if allowed["preferences"] else "Not used - permission off. Day order follows observed productivity."},
        {"key": "behavior", "label": "Behavioral Patterns (Digital Twin)", "permitted": allowed["behavior"],
         "used": allowed["behavior"] and any(i["value"] != "Not enough evidence" for i in trait_items),
         "items": trait_items if allowed["behavior"] else [],
         "note": "" if allowed["behavior"] else "Not used - permission off. Neutral values were used instead."},
        {"key": "history", "label": "Study / Work History", "permitted": allowed["history"], "used": False,
         "items": [], "note": "Not read directly by the simulator - your learned traits summarize this activity."},
    ]
