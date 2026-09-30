from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BehaviorObservation, Preference, TwinSnapshot
from app.routers.users import get_user_or_404
from app.schemas import TwinResponse
from app.schemas.feedback import TwinUpdate
from app.services import access_log, pattern_analyzer, permission_gate

router = APIRouter(prefix="/api/twin", tags=["Digital Twin"])


def _twin_response(db: Session, user_id: int) -> dict:
    traits = pattern_analyzer.get_traits(db, user_id)

    obs = db.query(BehaviorObservation).filter(BehaviorObservation.user_id == user_id)
    total = obs.count()
    demo = obs.filter(BehaviorObservation.source == "demo").count()

    used_in_last_analysis = traits[0].details.get("observations_in_twin", 0) if traits else 0
    pref = db.query(Preference).filter(Preference.user_id == user_id).first()

    return {
        "user_id": user_id,
        "analyzed": bool(traits),
        "last_analyzed": max((t.last_updated for t in traits), default=None),
        "total_observations": total,
        "demo_observations": demo,
        "observations_pending_analysis": max(0, total - used_in_last_analysis),
        "stated_preference": (
            {
                "available_hours_per_day": pref.available_hours_per_day,
                "preferred_working_time": pref.preferred_working_time,
            }
            if pref
            else None
        ),
        "config": {
            "alpha": pattern_analyzer.ALPHA,
            "minimum_evidence": pattern_analyzer.MIN_EVIDENCE,
            "full_confidence_at": pattern_analyzer.CONFIDENCE_FULL_AT,
        },
        "traits": traits,
    }


@router.get("/{user_id}/traits", response_model=TwinResponse)
def get_twin_traits(user_id: int, db: Session = Depends(get_db)):
    """The Twin as last analyzed (stored traits). Does not run any calculation."""
    get_user_or_404(db, user_id)
    response = _twin_response(db, user_id)
    access_log.record(db, user_id, "twin_viewed", "twin", dedupe=True)
    return response


@router.post("/{user_id}/analyze", response_model=TwinResponse)
def analyze_twin(user_id: int, db: Session = Depends(get_db)):
    """Load observations -> run the Pattern Analyzer -> save traits -> return the updated Twin.
    Phase 6: refused while learning is paused or the Study / Work History permission is off."""
    get_user_or_404(db, user_id)
    try:
        permission_gate.require_learning(permission_gate.get_or_create(db, user_id))
    except permission_gate.PermissionDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    pattern_analyzer.analyze_user(db, user_id)
    access_log.record(db, user_id, "twin_updated", "twin", "rebuilt from stored observations")
    return _twin_response(db, user_id)


@router.get("/{user_id}/updates", response_model=List[TwinUpdate])
def get_twin_updates(user_id: int, limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    """Phase 5: the most recent learning updates (Twin Diff before -> after), newest first."""
    get_user_or_404(db, user_id)
    rows = (db.query(TwinSnapshot).filter(TwinSnapshot.user_id == user_id)
            .order_by(TwinSnapshot.id.desc()).limit(limit).all())
    return [{"snapshot_id": r.id, "feedback_id": r.feedback_id, "created_at": r.created_at,
             "reason": r.reason, "changes": r.changes} for r in rows]
