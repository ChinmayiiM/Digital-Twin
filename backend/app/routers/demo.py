from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.users import get_user_or_404
from app.services import demo_data, permission_gate

router = APIRouter(prefix="/api/demo", tags=["Demo data (synthetic)"])


@router.post("/seed/{user_id}")
def seed_demo(user_id: int, db: Session = Depends(get_db)):
    """Stores synthetic observations (source='demo'). Must be called explicitly - never automatic.
    It only stores observations; run POST /api/twin/{user_id}/analyze afterwards to build the traits."""
    get_user_or_404(db, user_id)
    permission_gate.enforce_history(db, user_id)
    if demo_data.demo_exists(db, user_id):
        raise HTTPException(status_code=409, detail="Demo data is already loaded for this user")
    count = demo_data.seed_demo_observations(db, user_id)
    return {"message": "Synthetic demo observations stored", "observations_created": count}


@router.delete("/seed/{user_id}")
def clear_demo(user_id: int, db: Session = Depends(get_db)):
    """Removes ONLY this user's synthetic (source='demo') observations. Real observations are untouched."""
    get_user_or_404(db, user_id)
    removed = demo_data.clear_demo_observations(db, user_id)
    return {"message": "Synthetic demo observations removed", "observations_removed": removed}
