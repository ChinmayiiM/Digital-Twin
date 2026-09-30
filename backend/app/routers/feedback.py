"""Phase 5 - feedback on a recommendation -> learning -> Twin update -> Twin Diff."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.users import get_user_or_404
from app.schemas.feedback import FeedbackCreate, FeedbackResponse
from app.services import access_log, feedback_learning, scenario_store

router = APIRouter(prefix="/api/feedback", tags=["Feedback & learning"])
log = logging.getLogger("twinmate.feedback")


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)):
    """Store feedback for a scenario. If it contains behavioral evidence (actual hours of a completed task,
    deadline outcome), the Twin is updated and the Twin Diff is returned - all in one transaction."""
    get_user_or_404(db, payload.user_id)
    scenario = scenario_store.get_run(db, payload.user_id, payload.scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="Scenario not found. Run the simulation again and give feedback on the new result.")
    try:
        result = feedback_learning.submit(db, payload, scenario)
    except feedback_learning.FeedbackError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    except SQLAlchemyError:
        log.exception("Feedback transaction failed")
        raise HTTPException(status_code=500, detail="The feedback could not be saved. Nothing was changed - please try again.")
    access_log.record(db, payload.user_id, "feedback_submitted", "feedback", f"scenario #{scenario.id}")
    if result["updated"]:
        access_log.record(db, payload.user_id, "twin_updated", "twin",
                          f"{len(result['changes'])} trait(s) changed from feedback")
    return result
