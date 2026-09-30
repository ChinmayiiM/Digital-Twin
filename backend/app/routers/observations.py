from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BehaviorObservation, Task
from app.routers.users import get_user_or_404
from app.schemas import ObservationCreate, ObservationResponse
from app.services import permission_gate

router = APIRouter(prefix="/api/observations", tags=["Observations (Twin memory)"])


@router.post("", response_model=ObservationResponse, status_code=status.HTTP_201_CREATED)
def create_observation(payload: ObservationCreate, db: Session = Depends(get_db)):
    """Store one piece of behavioral evidence. It only becomes part of the Twin after
    POST /api/twin/{user_id}/analyze is run."""
    get_user_or_404(db, payload.user_id)
    permission_gate.enforce_history(db, payload.user_id)
    if payload.task_id is not None:
        task = db.get(Task, payload.task_id)
        if task is None or task.user_id != payload.user_id:
            raise HTTPException(status_code=400, detail="task_id does not belong to this user")
    observation = BehaviorObservation(**payload.model_dump())
    db.add(observation)
    db.commit()
    db.refresh(observation)
    return observation


@router.get("/user/{user_id}", response_model=List[ObservationResponse])
def list_observations(user_id: int, limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db)):
    """Newest first. Only this user's observations are ever returned."""
    get_user_or_404(db, user_id)
    return (
        db.query(BehaviorObservation)
        .filter(BehaviorObservation.user_id == user_id)
        .order_by(BehaviorObservation.id.desc())
        .limit(limit)
        .all()
    )
