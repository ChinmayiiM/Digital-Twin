"""Schemas for Phase 5 - feedback -> learning -> Twin update -> Twin Diff."""
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

Rating = Literal["helpful", "partially_helpful", "not_helpful"]
ReasonTag = Literal[
    "matched_situation", "estimate_accurate", "task_took_longer", "task_faster",
    "deadline_changed", "schedule_changed", "prefer_other_option", "other",
]

MAX_ACTUAL_HOURS = 100  # one task, one feedback - anything above is almost certainly a typo


class FeedbackCreate(BaseModel):
    user_id: int
    scenario_id: int
    rating: Rating
    reasons: List[ReasonTag] = Field(default_factory=list)
    task_id: Optional[int] = None  # which task the actual outcome is about
    actual_hours: Optional[float] = Field(default=None, gt=0, le=MAX_ACTUAL_HOURS, allow_inf_nan=False)
    completed: Optional[bool] = None
    deadline_met: Optional[bool] = None
    hours_late: Optional[float] = Field(default=None, ge=0, le=720, allow_inf_nan=False)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def check_outcome(self):
        self.reasons = list(dict.fromkeys(self.reasons))
        self.notes = (self.notes or "").strip() or None
        has_outcome = any(v is not None for v in (self.actual_hours, self.completed, self.deadline_met, self.hours_late))
        if has_outcome and self.task_id is None:
            raise ValueError("Choose which task the actual outcome is about")
        if self.hours_late is not None and self.deadline_met is not False:
            raise ValueError("Hours late can only be given when the deadline was not met")
        if self.completed is False and self.deadline_met is True:
            raise ValueError("A task that is not completed cannot have met its deadline")
        return self


class ObservationCreated(BaseModel):
    observation_id: int
    observation_type: str
    observed_value: float
    description: str


class Interpretation(BaseModel):
    evidence_found: bool
    observations: List[ObservationCreated]
    notes: List[str]  # what TwinMate used, and what it deliberately did NOT use (and why)
    note_category: Optional[str] = None
    understood_by: Literal["rules", "llm"] = "rules"


class TraitChange(BaseModel):
    trait_name: str
    label: str
    before_value: Optional[float] = None
    after_value: Optional[float] = None
    change: Optional[float] = None
    before_short: str
    after_short: str
    confidence_before: float
    confidence_after: float
    confidence_label_before: str
    confidence_label_after: str
    evidence_before: int
    evidence_after: int
    significant: bool
    reason: str
    formula: Optional[str] = None


class LearningStep(BaseModel):
    step: str
    title: str
    detail: str


class FeedbackResponse(BaseModel):
    feedback_id: int
    scenario_id: int
    recorded: bool
    updated: bool
    message: str
    interpretation: Interpretation
    changes: List[TraitChange]
    snapshot_id: Optional[int] = None
    learning_steps: List[LearningStep]
    learning_blocked: Optional[str] = None  # Phase 6: set when learning is paused / history permission is off


class TwinUpdate(BaseModel):
    snapshot_id: int
    feedback_id: Optional[int] = None
    created_at: datetime
    reason: str
    changes: List[TraitChange]
