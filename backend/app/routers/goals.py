from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Goal
from app.routers.users import get_user_or_404
from app.services.permission_gate import check_owner, request_user_id
from app.schemas import GoalCreate, GoalResponse

router = APIRouter(prefix="/api/goals", tags=["Goals"])


@router.post("", response_model=GoalResponse, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)):
    get_user_or_404(db, payload.user_id)
    goal = Goal(**payload.model_dump())
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/user/{user_id}", response_model=List[GoalResponse])
def list_goals(user_id: int, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.query(Goal).filter(Goal.user_id == user_id).order_by(Goal.id).all()


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int, db: Session = Depends(get_db), caller: str = Depends(request_user_id)):
    goal = db.get(Goal, goal_id)
    if goal is None:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    check_owner(goal.user_id, caller)
    db.delete(goal)  # tasks linked to this goal keep existing with goal_id = NULL
    db.commit()
