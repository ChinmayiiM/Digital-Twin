"""The What-If workflow in one place - one plain function per step, run in order:

    1 UNDERSTAND  scenario_parser     question -> structured intent (LLM optional, rules fallback)
    2 PLAN        scenario_planner    intent + real tasks -> Plan A / B / C
    3 SIMULATE    scenario_simulator  Twin + plans -> typical run + Monte Carlo (NumPy)
    4 COMPARE     scenario_comparator side-by-side metrics + trade-offs
    5 DECIDE      recommender         explicit score -> recommended plan (or "no clear preference")
    6 EXPLAIN     llm_explainer       LLM wording of the calculated result, or deterministic fallback

Each step's real duration and a short summary are returned as "workflow", so the UI can show
exactly what happened (nothing is animated or faked).
"""
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.services import (
    llm_explainer,
    recommender,
    scenario_comparator,
    scenario_parser,
    scenario_planner,
    scenario_simulator,
    simulation_config as cfg,
    twin_context,
)


class _Timer:
    def __init__(self):
        self.steps = []

    def add(self, step: str, title: str, detail: str, started: float):
        self.steps.append({"step": step, "title": title, "detail": detail,
                           "duration_ms": round((time.perf_counter() - started) * 1000, 1)})


def _day_label(d) -> str:
    return d.strftime("%a, %b %d").replace(" 0", " ")


def analyze(db: Session, user_id: int, question: str, now: Optional[datetime] = None) -> dict:
    """Step 1 only (used by POST /api/simulator/analyze)."""
    ctx = twin_context.build_context(db, user_id)
    return {"question": question, **scenario_parser.parse_question(question, ctx, now)}


def run(db: Session, user_id: int, question: str, now: Optional[datetime] = None) -> dict:
    timer = _Timer()

    # ---------------- 1. UNDERSTAND ----------------
    t0 = time.perf_counter()
    ctx = twin_context.build_context(db, user_id)
    parsed = scenario_parser.parse_question(question, ctx, now)
    response = {"question": question, **parsed}
    intent = parsed["intent"]
    if parsed["status"] != "ok":
        timer.add("understand", "Understanding your decision",
                  {"clarification_needed": "More information needed", "over_capacity": "Capacity problem found",
                   "not_enough_data": "Not enough data to simulate"}[parsed["status"]], t0)
        response["workflow"] = timer.steps
        return response
    day_word = "today" if intent["time_horizon"] == "today" else "tomorrow"
    timer.add("understand", "Question understood",
              f"Focus: {intent['focus_task_title']} · Postpone: {', '.join(intent['deferred_task_titles'])}"
              f"{' (implied)' if intent['deferred_is_implicit'] else ''} · {day_word.capitalize()} "
              f"({_day_label(intent['start_date'])}) · understood by {'LLM' if parsed['understood_by'] == 'llm' else 'rules'}",
              t0)

    # ---------------- 2. PLAN ----------------
    t0 = time.perf_counter()
    tasks = scenario_planner.simulation_tasks(ctx, intent)
    days = scenario_planner.simulation_days(tasks, intent["start_date"])
    plans = scenario_planner.build_plans(ctx, intent, tasks)
    timer.add("plan", f"{len(plans)} plans created",
              f"Built from {len(tasks)} task(s) with deadlines between {_day_label(days[0])} and {_day_label(days[-1])}",
              t0)

    # ---------------- 3. SIMULATE ----------------
    t0 = time.perf_counter()
    results = scenario_simulator.simulate_plans(plans, tasks, days, ctx)
    windows = scenario_simulator.deadline_windows(tasks, days, ctx)
    timer.add("simulate", f"{cfg.N_SIMULATIONS * len(plans):,} simulations completed",
              f"{cfg.N_SIMULATIONS:,} Monte Carlo runs per plan over {len(days)} day(s), NumPy seed {cfg.RANDOM_SEED}",
              t0)

    # ---------------- 4. COMPARE ----------------
    t0 = time.perf_counter()
    comparison = scenario_comparator.compare(results, ctx, day_word)
    timer.add("compare", "Comparison complete", f"{len(comparison['rows'])} metrics compared across {len(results)} plans", t0)

    # ---------------- 5. DECIDE ----------------
    t0 = time.perf_counter()
    recommendation = recommender.recommend(results, plans, tasks, ctx, intent, windows)
    chosen = next((r for r in results if r["id"] == recommendation["recommended_plan_id"]), None)
    confidence = recommender.confidence_info(ctx, chosen or next(r for r in results if r["is_user_proposal"]))
    best_score = max(s["total"] for s in recommendation["scores"])
    timer.add("decide", "Recommendation ready",
              (f"{recommendation['headline']} (score {best_score:.2f})" if chosen else
               "No clear preference - the top scores are within 0.03"), t0)

    # ---------------- 6. EXPLAIN ----------------
    t0 = time.perf_counter()
    explanation = llm_explainer.explain(question, results, recommendation, confidence)
    timer.add("explain", "Explanation prepared",
              "Written by the LLM from calculated results" if explanation["source"] == "llm"
              else "Generated from simulation results (no LLM used)", t0)

    response.update(
        workflow=timer.steps,
        plans=results,
        comparison=comparison,
        recommendation=recommendation,
        explanation=explanation,
        twin_data_used=recommender.twin_data_used(ctx),
        data_used=recommender.data_used(ctx, tasks),
        confidence=confidence,
        settings={"simulations_per_plan": cfg.N_SIMULATIONS, "random_seed": cfg.RANDOM_SEED,
                  "start_date": days[0], "end_date": days[-1], "days": len(days)},
        assumptions=_assumptions(ctx, intent, tasks, days, windows, day_word),
    )
    return response


def _assumptions(ctx, intent, tasks, days, windows, day_word) -> list:
    notes = [
        f"The simulation starts {day_word} ({_day_label(days[0])}) and runs until the last deadline "
        f"({_day_label(days[-1])}); time left today is not counted." if day_word == "tomorrow" else
        f"The simulation starts today ({_day_label(days[0])}) with your full {ctx['available_hours']:g} hours.",
        "Every task starts at 0% progress (TwinMate does not track partial progress yet).",
        "Work on a deadline day is assumed to happen before the deadline time.",
        "After the first day, every plan works on the task with the earliest deadline.",
        "Productivity is applied relative to your own average, because your estimation tendency was measured "
        "at your normal working speed (so it is not counted twice).",
    ]
    for w in windows:
        if w["ratio"] and w["ratio"] > 1:
            notes.append(f"Capacity check: work due by {w['task_title']}'s deadline needs about "
                         f"{w['required_hours']:.1f} h, but only about {w['effective_capacity']:.1f} effective hours "
                         "are available before it - no plan can fully avoid this.")
    included = {t.id for t in tasks}
    skipped = [t.title for t in ctx["open_tasks"] if t.id not in included]
    if skipped:
        notes.append("Not simulated (no deadline or outside the window): " + ", ".join(skipped) + ".")
    return notes
