"""Schemas for Phase 4 - What-If Decision Simulator.

Every number in these responses is calculated in Python (services/scenario_simulator.py etc.).
The LLM (if configured) only fills ParsedIntent-like JSON and the explanation text.
"""
from datetime import date, datetime
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, StringConstraints

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]
Status = Literal["ok", "clarification_needed", "over_capacity", "not_enough_data"]


class SimulatorRequest(BaseModel):
    user_id: int
    question: Question


# ------------------------------------------------------------------ 1. UNDERSTAND
class LLMIntent(BaseModel):
    """The ONLY shape accepted from the LLM. Anything else is rejected and the rule parser is used."""

    intent: Literal["reschedule_work", "unclear"]
    focus_task_id: Optional[int] = None
    deferred_task_ids: List[int] = Field(default_factory=list)
    time_horizon: Literal["today", "tomorrow"] = "tomorrow"


class ParsedIntent(BaseModel):
    intent: Literal["reschedule_work", "over_capacity", "unclear"]
    focus_task_id: Optional[int] = None
    focus_task_title: Optional[str] = None
    deferred_task_ids: List[int] = Field(default_factory=list)
    deferred_task_titles: List[str] = Field(default_factory=list)
    deferred_is_implicit: bool = False  # True when the user did not name what gets postponed
    time_horizon: Literal["today", "tomorrow"] = "tomorrow"
    start_date: date
    requested_hours: Optional[float] = None
    matched_terms: List[str] = Field(default_factory=list)
    source: Literal["rules", "llm"] = "rules"


class CapacityCheck(BaseModel):
    requested_hours: float
    available_hours: float
    workload_ratio: float
    workload_label: str
    message: str


class AnalyzeResponse(BaseModel):
    status: Status
    question: str
    intent: Optional[ParsedIntent] = None
    message: Optional[str] = None
    suggestions: List[str] = Field(default_factory=list)
    capacity: Optional[CapacityCheck] = None
    understood_by: Literal["rules", "llm"] = "rules"


# ------------------------------------------------------------------ 2-3. PLAN + SIMULATE
class DayBlock(BaseModel):
    task_id: int
    task_title: str
    hours: float


class DaySchedule(BaseModel):
    date: date
    label: str
    blocks: List[DayBlock]
    idle_hours: float
    switch_hours: float


class TaskOutcome(BaseModel):
    task_id: int
    title: str
    priority: str
    deadline: datetime
    estimated_hours: float
    adjusted_required_hours: float
    expected_progress: float  # 0..1 progress reached BEFORE the deadline (Monte Carlo mean)
    progress_low: float  # 10th percentile
    progress_high: float  # 90th percentile
    on_time_probability: float
    deadline_risk: float  # 1 - on_time_probability
    risk_label: str
    hours_before_deadline: float  # clock hours this plan gives the task before its deadline (typical run)


class PlanResult(BaseModel):
    id: str
    key: str
    name: str
    description: str
    is_user_proposal: bool
    first_day_switches: int
    tasks: List[TaskOutcome]
    overall_expected: float
    overall_low: float
    overall_high: float
    max_deadline_risk: float
    risk_label: str
    workload_ratio: float
    workload_label: str
    capacity_usage: float
    schedule: List[DaySchedule]


# ------------------------------------------------------------------ 4. COMPARE
class ComparisonRow(BaseModel):
    metric: str
    kind: Literal["percent", "label", "ratio", "range"]
    values: Dict[str, str]  # plan id -> display text
    raw: Dict[str, float]  # plan id -> number


class Comparison(BaseModel):
    plan_ids: List[str]
    plan_names: Dict[str, str]
    rows: List[ComparisonRow]
    trade_offs: Dict[str, List[str]]


# ------------------------------------------------------------------ 5. DECIDE
class ScoreBreakdown(BaseModel):
    plan_id: str
    progress: float
    on_time: float
    risk_penalty: float
    overload_penalty: float
    habit_bonus: float
    total: float


class Recommendation(BaseModel):
    recommended_plan_id: Optional[str] = None
    recommended_plan_name: Optional[str] = None
    no_clear_preference: bool
    headline: str
    reasons: List[str]
    trade_offs: List[str]
    scores: List[ScoreBreakdown]
    formula: str


# ------------------------------------------------------------------ 6. EXPLAIN + transparency
class Explanation(BaseModel):
    text: str
    source: Literal["llm", "simulation_results"]
    label: str


class TwinDataItem(BaseModel):
    label: str
    value: str
    source: Literal["profile", "twin", "fallback", "not_permitted"]
    confidence: Optional[float] = None
    evidence_count: Optional[int] = None
    used_for: str


class DataUsedItem(BaseModel):
    name: str
    value: str
    detail: str


class DataUsedCategory(BaseModel):
    key: str
    label: str
    permitted: bool
    used: bool
    items: List[DataUsedItem]
    note: str


class ConfidenceInfo(BaseModel):
    score: float
    label: Literal["Low", "Moderate", "High"]
    evidence_count: int
    limited_evidence: bool
    message: str
    expected_outcome: float
    outcome_low: float
    outcome_high: float


class WorkflowStep(BaseModel):
    step: str
    title: str
    detail: str
    duration_ms: float


class SimulationSettings(BaseModel):
    simulations_per_plan: int
    random_seed: int
    start_date: date
    end_date: date
    days: int


class RerunRequest(BaseModel):
    user_id: int


class TwinValueChange(BaseModel):
    label: str
    before: str
    after: str
    evidence_before: Optional[int] = None
    evidence_after: Optional[int] = None


class TaskHoursChange(BaseModel):
    task_id: int
    title: str
    estimated_before: float
    estimated_after: float
    adjusted_before: float
    adjusted_after: float


class PlanOutcomeChange(BaseModel):
    plan_id: str
    plan_name: str
    task_title: str
    on_time_before: float
    on_time_after: float


class LearningEffect(BaseModel):
    """Re-run vs. original run of the same question (both calculated by the simulator)."""

    previous_scenario_id: int
    previous_recommendation: Optional[str] = None
    current_recommendation: str
    recommendation_changed: bool
    twin_changes: List[TwinValueChange]
    task_changes: List[TaskHoursChange]
    plan_changes: List[PlanOutcomeChange]
    message: str


class RunResponse(AnalyzeResponse):
    scenario_id: Optional[int] = None  # Phase 5: stored run that feedback can refer to
    rerun_of: Optional[int] = None
    learning_effect: Optional[LearningEffect] = None
    workflow: List[WorkflowStep] = Field(default_factory=list)
    plans: List[PlanResult] = Field(default_factory=list)
    comparison: Optional[Comparison] = None
    recommendation: Optional[Recommendation] = None
    explanation: Optional[Explanation] = None
    twin_data_used: List[TwinDataItem] = Field(default_factory=list)
    data_used: List[DataUsedCategory] = Field(default_factory=list)
    confidence: Optional[ConfidenceInfo] = None
    settings: Optional[SimulationSettings] = None
    assumptions: List[str] = Field(default_factory=list)
