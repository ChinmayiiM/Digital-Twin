from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Goal, Task
from app.routers.users import get_user_or_404
from app.services.permission_gate import check_owner, request_user_id
from app.schemas import TaskCreate, TaskResponse, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])

# These columns are NOT NULL, so an explicit null in a PUT body is rejected.
_REQUIRED_ON_UPDATE = ("title", "estimated_hours", "priority", "status")


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    get_user_or_404(db, payload.user_id)
    if payload.goal_id is not None:
        goal = db.get(Goal, payload.goal_id)
        if goal is None or goal.user_id != payload.user_id:
            raise HTTPException(status_code=400, detail="goal_id does not belong to this user")
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/user/{user_id}", response_model=List[TaskResponse])
def list_tasks(user_id: int, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    return db.query(Task).filter(Task.user_id == user_id).order_by(Task.id).all()


@router.put("/{task_id}", response_model=TaskResponse)
def update_task(task_id: int, payload: TaskUpdate, db: Session = Depends(get_db),
    caller: str = Depends(request_user_id)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    check_owner(task.user_id, caller)

    changes = payload.model_dump(exclude_unset=True)
    for field in _REQUIRED_ON_UPDATE:
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=422, detail=f"{field} cannot be null")
    for field, value in changes.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db), caller: str = Depends(request_user_id)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    check_owner(task.user_id, caller)
    db.delete(task)
    db.commit()
