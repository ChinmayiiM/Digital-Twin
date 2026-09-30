from typing import List, Optional

from pydantic import BaseModel

from app.schemas.goal import GoalResponse
from app.schemas.task import TaskResponse
from app.schemas.user import UserResponse


class DashboardResponse(BaseModel):
    user: UserResponse
    goals_count: int
    tasks_count: int
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks: int
    available_hours_per_day: Optional[float] = None
    preferred_working_time: Optional[str] = None
    upcoming_tasks: List[TaskResponse]
    goals: List[GoalResponse]
    tasks: List[TaskResponse]
