"""Step 1 - UNDERSTAND the what-if question.

Turns free text into a structured intent:
    focus task      the task the user wants to spend the day on
    deferred tasks  the task(s) being postponed
    time horizon    today / tomorrow
    requested hours (only when the user names a number, e.g. "20 hours")

Two ways to understand, tried in this order:
  1. LLM (only if configured in .env). It must return JSON matching schemas.simulator.LLMIntent,
     and every task id it returns must be one of THIS user's open tasks. Otherwise it is ignored.
  2. Rules (always available). Task names are matched against the user's own task + goal titles,
     and cue words ("postpone", "only", "focus", "instead of" ...) decide which task is focused
     and which is postponed.

If the question does not clearly point at a task, we ask for clarification instead of guessing.
Numbers (hours) are always read by Python, never by the LLM.
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from pydantic import ValidationError

from app.schemas.simulator import LLMIntent
from app.services import llm_client
from app.services.simulation_config import workload_label

# ------------------------------------------------------------------ word handling
_SUFFIXES = ("ations", "ation", "ings", "ing", "ions", "ion", "ments", "ment", "ed", "es", "s", "e")


def stem(word: str) -> str:
    """Very small stemmer: preparing / preparation / prepare -> 'prepar'."""
    word = word.lower()
    for suffix in _SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def words(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


# Words that never identify a specific task.
_GENERIC = {stem(w) for w in (
    "a an the my your our for of to and on in at with by i me it this that task tasks work working "
    "complete finish do doing get make new final all some more"
).split()}

# Question word -> word that may appear in a task title.
_SYNONYMS = {stem(k): stem(v) for k, v in {
    "test": "exam", "examination": "exam", "revision": "exam", "revise": "exam", "revising": "exam",
    "homework": "assignment", "hw": "assignment",
}.items()}

_DEFER_WORDS = {stem(w) for w in (
    "postpone postponing delay delaying defer skip later push leave ignore drop pause procrastinate neglect wait"
).split()}
_DEFER_PHRASES = ("put off", "hold off", "put aside", "set aside", "don't do", "dont do", "not do", "without")
_FORCED_DEFER_SPLITS = ("instead of", "rather than", "over", "not", "before")  # text AFTER these is postponed
_CLAUSE_SPLIT = re.compile(
    r"(,|;|\band\b|\bbut\b|\bthen\b|\bwhile\b|\binstead of\b|\brather than\b|\bover\b|\bnot\b|\bbefore\b)"
)

_ALL_WORK = re.compile(r"\b(all (of )?(my )?(the )?(work|tasks|assignments|pending)|everything|every task)\b")
_HOURS = re.compile(r"(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\b")


# ------------------------------------------------------------------ task keywords
def _task_keywords(tasks, use_goals: bool = True) -> Dict[int, Set[str]]:
    """Distinctive stems per task: words from the task title (and its goal title, if the Goals permission
    is on) that belong to ONE task."""
    raw = {}
    for t in tasks:
        text = t.title + " " + (t.goal.title if (use_goals and t.goal is not None) else "")
        raw[t.id] = {stem(w) for w in words(text)} - _GENERIC
    if len(tasks) == 1:
        return raw
    counts: Dict[str, int] = {}
    for stems in raw.values():
        for s in stems:
            counts[s] = counts.get(s, 0) + 1
    return {tid: {s for s in stems if counts[s] == 1} for tid, stems in raw.items()}


def _question_stems(clause: str, known: Set[str]) -> Dict[str, str]:
    """stem -> original word, with synonyms mapped onto words that really exist in the user's tasks."""
    result = {}
    for w in words(clause):
        s = stem(w)
        if s not in known and _SYNONYMS.get(s) in known:
            s = _SYNONYMS[s]
        result[s] = w
    return result


def _split_clauses(question: str) -> List[Tuple[str, bool]]:
    """[(clause_text, forced_defer)] - a clause after 'instead of' / 'rather than' / 'over' / 'not' is postponed."""
    parts = _CLAUSE_SPLIT.split(question.lower())
    clauses, forced = [], False
    for part in parts:
        token = part.strip()
        if _CLAUSE_SPLIT.fullmatch(token or " "):
            forced = token in _FORCED_DEFER_SPLITS
            continue
        if token:
            clauses.append((token, forced))
        forced = False
    return clauses


def _rule_intent(question: str, tasks, use_goals: bool = True) -> dict:
    keywords = _task_keywords(tasks, use_goals)
    known = set().union(*keywords.values()) if keywords else set()
    focus, defer, matched = [], [], []

    for clause, forced_defer in _split_clauses(question):
        stems = _question_stems(clause, known)
        mentioned = [tid for tid, kws in keywords.items() if kws & stems.keys()]
        for tid in mentioned:
            matched += [stems[s] for s in keywords[tid] & stems.keys()]
        is_defer = forced_defer or bool(_DEFER_WORDS & stems.keys()) or any(p in clause for p in _DEFER_PHRASES)
        (defer if is_defer else focus).extend(mentioned)

    defer_ids = list(dict.fromkeys(defer))
    focus_ids = [t for t in dict.fromkeys(focus) if t not in defer_ids]
    return {"focus": focus_ids, "defer": defer_ids, "matched": list(dict.fromkeys(matched))}


# ------------------------------------------------------------------ LLM (optional)
_LLM_SYSTEM = (
    "You convert a person's what-if question about their schedule into JSON. You never calculate anything. "
    "Reply with ONE JSON object only, no other text, with keys: "
    '"intent" ("reschedule_work" or "unclear"), "focus_task_id" (integer or null), '
    '"deferred_task_ids" (list of integers), "time_horizon" ("today" or "tomorrow"). '
    "Use only task ids from the provided list. If the question does not clearly name or clearly imply a "
    'specific task to focus on or postpone, use "unclear". Do not guess.'
)


def _llm_intent(question: str, tasks, use_goals: bool = True) -> Optional[dict]:
    if not llm_client.is_configured():
        return None
    task_list = [{"id": t.id, "title": t.title, "goal": t.goal.title if (use_goals and t.goal is not None) else None,
                  "deadline": t.deadline.isoformat() if t.deadline else None} for t in tasks]
    reply = llm_client.complete(_LLM_SYSTEM, json.dumps({"question": question, "tasks": task_list}), max_tokens=200)
    data = llm_client.extract_json(reply)
    if data is None:
        return None
    try:
        parsed = LLMIntent.model_validate(data)
    except ValidationError:
        return None  # malformed LLM output -> rules take over
    ids = {t.id for t in tasks}
    if parsed.intent != "reschedule_work":
        return None
    if parsed.focus_task_id is not None and parsed.focus_task_id not in ids:
        return None
    if any(d not in ids or d == parsed.focus_task_id for d in parsed.deferred_task_ids):
        return None
    if parsed.focus_task_id is None and not parsed.deferred_task_ids:
        return None
    return {"focus": [parsed.focus_task_id] if parsed.focus_task_id else [],
            "defer": list(dict.fromkeys(parsed.deferred_task_ids)), "matched": [],
            "time_horizon": parsed.time_horizon}


# ------------------------------------------------------------------ public entry point
def _suggestions(tasks) -> List[str]:
    dated = [t for t in tasks if t.deadline is not None]
    if len(dated) >= 2:
        a, b = dated[0], dated[1]
        return [f"What if I spend tomorrow only on {b.title} and postpone {a.title}?",
                f"What if I postpone {b.title} and finish {a.title} first?"]
    if dated:
        return [f"What if I spend tomorrow only on {dated[0].title}?"]
    return []


def parse_question(question: str, ctx: dict, now: Optional[datetime] = None) -> dict:
    """Returns {"status", "intent" (dict or None), "message", "suggestions", "capacity", "understood_by"}."""
    now = now or datetime.now()
    tasks = ctx["open_tasks"]
    text = question.lower()
    result = {"status": "ok", "intent": None, "message": None, "suggestions": [], "capacity": None,
              "understood_by": "rules"}

    blocked = [label for key, label in (("timetable", "Timetable & Available Hours"), ("tasks", "Tasks & Deadlines"))
               if not ctx["permissions"][key]]
    if blocked:
        result.update(status="not_enough_data",
                      message=f"The {' and '.join(blocked)} permission{'s are' if len(blocked) > 1 else ' is'} off, "
                              "so TwinMate cannot simulate your schedule. Turn it on in Privacy & Data.")
        return result
    if not ctx["has_preferences"]:
        result.update(status="not_enough_data",
                      message="Please set your available hours per day first (onboarding), so TwinMate knows your capacity.")
        return result

    horizon = "today" if re.search(r"\b(today|tonight)\b", text) else "tomorrow"
    start_date = now.date() + timedelta(days=0 if horizon == "today" else 1)
    available = ctx["available_hours"]
    ratio = ctx["estimation"]["ratio"]

    # ---- capacity questions: "20 hours tomorrow" / "all my work tomorrow" (numbers read by Python) ----
    hours_match = _HOURS.search(text)
    requested, basis = None, ""
    if hours_match:
        requested, basis = float(hours_match.group(1)), "as stated in your question"
    elif _ALL_WORK.search(text) and tasks:
        requested = round(sum(t.estimated_hours for t in tasks) * ratio, 1)
        basis = (f"your {len(tasks)} open tasks, adjusted by your Twin's estimation tendency (x{ratio:.2f})"
                 if ctx["estimation"]["info"]["source"] == "twin" else f"your {len(tasks)} open tasks")
    if requested is not None and requested > available:
        load = requested / available
        result.update(status="over_capacity", suggestions=_suggestions(tasks), capacity={
            "requested_hours": requested, "available_hours": available,
            "workload_ratio": round(load, 2), "workload_label": workload_label(load),
            "message": (f"This plan requires approximately {requested:g} hours ({basis}), but your current "
                        f"available capacity is {available:g} hours/day. The scenario is therefore over capacity "
                        f"(workload ratio {load:.2f})."),
        })
        result["intent"] = {"intent": "over_capacity", "time_horizon": horizon, "start_date": start_date,
                            "requested_hours": requested}
        result["message"] = result["capacity"]["message"]
        return result

    if len(tasks) < 2:
        result.update(status="not_enough_data", suggestions=_suggestions(tasks),
                      message="The simulator compares plans between at least two open tasks. "
                              "Add another task (with a deadline) on the onboarding page first.")
        return result

    # ---- understand: LLM first (if configured and valid), rules otherwise ----
    found = _llm_intent(question, tasks, ctx["use_goals"])
    if found:
        result["understood_by"] = "llm"
        horizon = found["time_horizon"]
        start_date = now.date() + timedelta(days=0 if horizon == "today" else 1)
    else:
        found = _rule_intent(question, tasks, ctx["use_goals"])

    by_id = {t.id: t for t in tasks}
    focus, defer = found["focus"], found["defer"]
    clarify = None
    if not focus and not defer:
        clarify = "I need a little more information. Which task or goal would you like to prioritize " + \
                  ("today?" if horizon == "today" else "tomorrow?")
    elif len(focus) > 1:
        names = " or ".join(by_id[t].title for t in focus)
        clarify = f"Which task should come first: {names}? Tell me which one you would postpone."

    deferred_implicit = False
    if not clarify:
        dated_others = lambda exclude: [t for t in tasks if t.deadline is not None and t.id not in exclude]  # noqa: E731
        if not focus:  # "What if I postpone X?" -> the day goes to the nearest-deadline other task
            others = dated_others(set(defer))
            if others:
                focus = [others[0].id]
        if not defer:  # "What if I focus only on X?" -> the competing task is the nearest other deadline
            others = dated_others(set(focus))
            if others:
                defer, deferred_implicit = [others[0].id], True
        if not focus or not defer:
            clarify = "I couldn't find two tasks with deadlines to compare. Which task would you postpone?"

    if not clarify:
        for tid in focus + defer:
            t = by_id[tid]
            if t.deadline is None:
                clarify = f'"{t.title}" has no deadline, so its deadline risk cannot be simulated. Please add one.'
                break
            if t.deadline.date() < start_date:
                clarify = (f'"{t.title}" is due before {"today" if horizon == "today" else "tomorrow"} '
                           f'({t.deadline:%b %d, %I:%M %p}), so it cannot be part of this plan. '
                           "Update its deadline or status first.")
                break

    if clarify:
        result.update(status="clarification_needed", message=clarify, suggestions=_suggestions(tasks))
        result["intent"] = {"intent": "unclear", "time_horizon": horizon, "start_date": start_date,
                            "matched_terms": found.get("matched", [])}
        return result

    result["intent"] = {
        "intent": "reschedule_work",
        "focus_task_id": focus[0], "focus_task_title": by_id[focus[0]].title,
        "deferred_task_ids": defer, "deferred_task_titles": [by_id[d].title for d in defer],
        "deferred_is_implicit": deferred_implicit,
        "time_horizon": horizon, "start_date": start_date,
        "requested_hours": float(hours_match.group(1)) if hours_match else None,
        "matched_terms": found.get("matched", []),
        "source": result["understood_by"],
    }
    return result
