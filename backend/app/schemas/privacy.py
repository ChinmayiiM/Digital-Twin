"""Schemas for Phase 6 - privacy, permissions, learning pause, forget, data used, export, access logs."""
from datetime import datetime
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.schemas.simulator import DataUsedCategory

ForgetCategory = Literal["tasks", "goals", "preferences", "observations", "patterns", "history"]


class PermissionState(BaseModel):
    timetable: bool
    goals: bool
    tasks: bool
    history: bool
    preferences: bool
    behavior: bool


class PermissionUpdate(BaseModel):
    """Send only the switches that change, e.g. {"behavior": false}."""

    timetable: Optional[bool] = None
    goals: Optional[bool] = None
    tasks: Optional[bool] = None
    history: Optional[bool] = None
    preferences: Optional[bool] = None
    behavior: Optional[bool] = None

    @model_validator(mode="after")
    def at_least_one(self):
        if all(v is None for v in self.model_dump().values()):
            raise ValueError("Send at least one permission to change")
        return self


class LearningUpdate(BaseModel):
    paused: bool


class ForgetRequest(BaseModel):
    categories: List[ForgetCategory] = Field(min_length=1)
    confirm: bool = False  # destructive: must be explicitly true

    @model_validator(mode="after")
    def must_confirm(self):
        if not self.confirm:
            raise ValueError("Please confirm before TwinMate forgets data (confirm must be true)")
        self.categories = list(dict.fromkeys(self.categories))
        return self


class PrivacyResponse(BaseModel):
    user_id: int
    permissions: PermissionState
    permission_labels: Dict[str, str]
    learning_paused: bool
    learning_message: str
    inventory: Dict[str, int]
    message: Optional[str] = None


class ForgetResponse(BaseModel):
    forgotten: Dict[str, int]
    message: str
    notes: List[str]


class DataUsedResponse(BaseModel):
    scenario_id: Optional[int] = None
    question: Optional[str] = None
    created_at: Optional[datetime] = None
    categories: List[DataUsedCategory]
    message: str


class AccessLogItem(BaseModel):
    id: int
    action: str
    text: str
    resource: str
    detail: str
    created_at: datetime
