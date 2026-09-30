"""Step 6 - EXPLAIN the calculated recommendation in plain language.

The explanation always starts from the numbers Python already calculated.
    * LLM configured  -> the LLM rewrites those facts into a short paragraph.
                         Guard: if the reply contains ANY number that is not in the facts we sent,
                         it is rejected (the LLM may not invent hours, probabilities or deadlines).
    * otherwise / rejected / timeout -> a deterministic sentence built from the same facts.
"""
import json
import re
from typing import List

from app.services import llm_client

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

_SYSTEM = (
    "You explain a schedule recommendation to a student in 3 or 4 short sentences. "
    "Use ONLY the facts in the JSON you receive. Do not add, change, round or calculate any number. "
    "Do not change which plan is recommended. Mention the main trade-off. Plain text, no lists, no markdown."
)


def _pct(x: float) -> str:
    return f"{round(x * 100)}%"


def _facts(question: str, results: List[dict], recommendation: dict, confidence: dict) -> dict:
    return {
        "question": question,
        "recommendation": recommendation["headline"],
        "no_clear_preference": recommendation["no_clear_preference"],
        "reasons": recommendation["reasons"],
        "trade_offs": recommendation["trade_offs"],
        "plans": [
            {"plan": f"Plan {r['id']} - {r['name']}", "proposed_by_user": r["is_user_proposal"],
             "expected_overall_progress": _pct(r["overall_expected"]),
             "likely_range": f"{_pct(r['overall_low'])} to {_pct(r['overall_high'])}",
             "worst_deadline_risk": r["risk_label"],
             "tasks": [{"task": t["title"], "chance_on_time": _pct(t["on_time_probability"])} for t in r["tasks"]]}
            for r in results
        ],
        "prediction_confidence": confidence["label"],
    }


def _numbers_are_from_facts(text: str, facts_json: str) -> bool:
    allowed = set(_NUMBER.findall(facts_json))
    return all(n in allowed for n in _NUMBER.findall(text))


def fallback_text(results: List[dict], recommendation: dict, scores: List[dict]) -> str:
    if recommendation["no_clear_preference"]:
        return (" ".join(recommendation["reasons"]) +
                " Compare the trade-offs of each plan below and choose the goal that matters most to you.")
    best = next(r for r in results if r["id"] == recommendation["recommended_plan_id"])
    proposed = next(r for r in results if r["is_user_proposal"])
    score = {s["plan_id"]: s["total"] for s in scores}
    text = (f"Plan {best['id']} is recommended because it has the highest recommendation score "
            f"({score[best['id']]:.2f}): it reaches {_pct(best['overall_expected'])} expected progress across your "
            f"tasks with {best['risk_label'].lower()} worst-case deadline risk.")
    if best["id"] != proposed["id"]:
        text += (f" Your proposed Plan {proposed['id']} scores {score[proposed['id']]:.2f} "
                 f"with {proposed['risk_label'].lower()} deadline risk.")
    if recommendation["trade_offs"]:
        text += f" The main trade-off: {recommendation['trade_offs'][0]}"
    return text


def explain(question: str, results: List[dict], recommendation: dict, confidence: dict) -> dict:
    facts = _facts(question, results, recommendation, confidence)
    facts_json = json.dumps(facts)
    reply = llm_client.complete(_SYSTEM, facts_json, max_tokens=300)
    if reply and _numbers_are_from_facts(reply, facts_json):
        return {"text": reply, "source": "llm",
                "label": f"Explanation written by an LLM ({llm_client.model_name()}) from TwinMate's calculated "
                         "results. All numbers come from the Python simulation."}
    return {"text": fallback_text(results, recommendation, recommendation["scores"]),
            "source": "simulation_results", "label": "Explanation generated from simulation results."}
