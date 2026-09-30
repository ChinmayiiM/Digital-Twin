from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.common import Priority, Title


class GoalCreate(BaseModel):
    user_id: int
    title: Title
    description: Optional[str] = None
    priority: Priority = "medium"


class GoalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    priority: str
    created_at: datetime
