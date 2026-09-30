from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Preference
from app.routers.users import get_user_or_404
from app.schemas import PreferenceCreate, PreferenceResponse

router = APIRouter(prefix="/api/preferences", tags=["Preferences"])


def _upsert(user_id: int, payload: PreferenceCreate, db: Session) -> Preference:
    get_user_or_404(db, user_id)
    pref = db.query(Preference).filter(Preference.user_id == user_id).first()
    if pref is None:
        pref = Preference(user_id=user_id)
        db.add(pref)
    pref.available_hours_per_day = payload.available_hours_per_day
    pref.preferred_working_time = payload.preferred_working_time
    db.commit()
    db.refresh(pref)
    return pref


@router.post("/{user_id}", response_model=PreferenceResponse)
def create_preferences(user_id: int, payload: PreferenceCreate, db: Session = Depends(get_db)):
    return _upsert(user_id, payload, db)


@router.put("/{user_id}", response_model=PreferenceResponse)
def update_preferences(user_id: int, payload: PreferenceCreate, db: Session = Depends(get_db)):
    return _upsert(user_id, payload, db)


@router.get("/{user_id}", response_model=PreferenceResponse)
def read_preferences(user_id: int, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    pref = db.query(Preference).filter(Preference.user_id == user_id).first()
    if pref is None:
        raise HTTPException(status_code=404, detail="Preferences not set for this user")
    return pref
