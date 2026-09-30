from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Goal, Preference, Task
from app.routers.users import get_user_or_404
from app.schemas import DashboardResponse

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


def _deadline_order(task: Task):
    # Earliest deadline first; tasks without a deadline go last.
    return (task.deadline is None, task.deadline or datetime.max, task.id)


@router.get("/{user_id}", response_model=DashboardResponse)
def get_dashboard(user_id: int, db: Session = Depends(get_db)):
    """Plain stored data and simple counts only - no Twin traits, predictions or simulation."""
    user = get_user_or_404(db, user_id)
    goals = db.query(Goal).filter(Goal.user_id == user_id).order_by(Goal.id).all()
    tasks = sorted(db.query(Task).filter(Task.user_id == user_id).all(), key=_deadline_order)
    pref = db.query(Preference).filter(Preference.user_id == user_id).first()

    upcoming = [t for t in tasks if t.status != "completed" and t.deadline is not None][:5]

    return {
        "user": user,
        "goals_count": len(goals),
        "tasks_count": len(tasks),
        "pending_tasks": sum(t.status == "pending" for t in tasks),
        "in_progress_tasks": sum(t.status == "in_progress" for t in tasks),
        "completed_tasks": sum(t.status == "completed" for t in tasks),
        "available_hours_per_day": pref.available_hours_per_day if pref else None,
        "preferred_working_time": pref.preferred_working_time if pref else None,
        "upcoming_tasks": upcoming,
        "goals": goals,
        "tasks": tasks,
    }
