from datetime import datetime
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

ObservationType = Literal["working_time", "task_estimation", "task_order", "delay", "focus_session"]
ObservationSource = Literal["user", "task_activity", "system", "demo"]

PERIODS = ("morning", "afternoon", "evening")


def _is_positive_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


class ObservationCreate(BaseModel):
    """What each observation type means:

    working_time     observed_value = productivity 0..1        context: {"time_period": "morning|afternoon|evening"}
    task_estimation  observed_value = ACTUAL hours spent       context: {"estimated_hours": 2.0}
    focus_session    observed_value = minutes of focused work  context: {} (optional)
    delay            observed_value = hours finished AFTER the deadline (0 = on time)
    task_order       observed_value = 1                        context: {"chosen": {...}, "remaining": [{...}]}
                     where each task is {"estimated_hours": 2, "priority": "low|medium|high", "deadline": "ISO date"}
    """

    user_id: int
    task_id: Optional[int] = None
    observation_type: ObservationType
    observed_value: float = Field(allow_inf_nan=False)
    context: Dict[str, Any] = Field(default_factory=dict)
    source: ObservationSource = "user"

    @model_validator(mode="after")
    def check_type_specific_rules(self):
        kind, value, ctx = self.observation_type, self.observed_value, self.context

        if kind == "working_time":
            if not 0 <= value <= 1:
                raise ValueError("working_time observed_value must be between 0 and 1 (e.g. 0.8 = 80%)")
            period = str(ctx.get("time_period", "")).strip().lower()
            if period not in PERIODS:
                raise ValueError("working_time needs context.time_period: morning, afternoon or evening")
            ctx["time_period"] = period

        elif kind == "task_estimation":
            if value <= 0:
                raise ValueError("task_estimation observed_value (actual hours) must be greater than 0")
            if not _is_positive_number(ctx.get("estimated_hours")):
                raise ValueError("task_estimation needs context.estimated_hours greater than 0")

        elif kind == "focus_session":
            if not 0 < value <= 600:
                raise ValueError("focus_session observed_value (minutes) must be between 0 and 600")

        elif kind == "delay":
            if value < 0:
                raise ValueError("delay observed_value (hours after deadline) cannot be negative; use 0 for on time")

        elif kind == "task_order":
            chosen, remaining = ctx.get("chosen"), ctx.get("remaining")
            if not isinstance(chosen, dict) or not _is_positive_number(chosen.get("estimated_hours")):
                raise ValueError("task_order needs context.chosen with estimated_hours")
            if not isinstance(remaining, list) or not remaining or not all(isinstance(r, dict) for r in remaining):
                raise ValueError("task_order needs context.remaining: a non-empty list of tasks")

        return self


class ObservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    task_id: Optional[int] = None
    observation_type: str
    observed_value: float
    context: Dict[str, Any]
    source: str
    created_at: datetime
