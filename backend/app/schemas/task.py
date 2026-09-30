from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Priority, Status, Title


def _reject_timezone(value: Optional[datetime]) -> Optional[datetime]:
    """Deadlines are stored as naive local date-times, so timezone offsets are refused
    instead of being silently shifted."""
    if value is not None and value.tzinfo is not None:
        raise ValueError("deadline must not include a timezone, e.g. 2026-10-01T18:00:00")
    return value


class TaskCreate(BaseModel):
    user_id: int
    goal_id: Optional[int] = None
    title: Title
    description: Optional[str] = None
    estimated_hours: float = Field(gt=0, le=500)
    deadline: Optional[datetime] = None
    priority: Priority = "medium"
    status: Status = "pending"

    _check_deadline = field_validator("deadline")(_reject_timezone)


class TaskUpdate(BaseModel):
    """Every field is optional; only the fields that are sent get changed."""

    title: Optional[Title] = None
    description: Optional[str] = None
    estimated_hours: Optional[float] = Field(default=None, gt=0, le=500)
    deadline: Optional[datetime] = None
    priority: Optional[Priority] = None
    status: Optional[Status] = None

    _check_deadline = field_validator("deadline")(_reject_timezone)


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    goal_id: Optional[int] = None
    title: str
    description: Optional[str] = None
    estimated_hours: float
    deadline: Optional[datetime] = None
    priority: str
    status: str
    created_at: datetime
