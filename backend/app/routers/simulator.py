"""Phase 4 - What-If Decision Simulator endpoints.

POST /api/simulator/analyze   step 1 only: how TwinMate understood the question
POST /api/simulator/run       full workflow: understand -> plan -> simulate -> compare -> decide -> explain
POST /api/simulator/rerun/{id} Phase 5: the SAME question again with the CURRENT (possibly updated) Twin

Successful runs are stored (scenario_runs) so feedback can refer to them. A re-run never reuses stored
numbers: it runs the whole Phase 4 pipeline again and only compares the new result with the old summary.

A question that needs clarification, is over capacity or lacks data is NOT an error:
it returns 200 with "status" set accordingly, so the UI can show the message.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.users import get_user_or_404
from app.schemas.simulator import AnalyzeResponse, RerunRequest, RunResponse, SimulatorRequest
from app.services import access_log, scenario_store, whatif_pipeline

router = APIRouter(prefix="/api/simulator", tags=["What-If Simulator"])
log = logging.getLogger("twinmate.simulator")


def _run_safely(db: Session, user_id: int, question: str) -> dict:
    """The Phase 4 pipeline, with a readable error if anything unexpected breaks inside it."""
    try:
        return whatif_pipeline.run(db, user_id, question)
    except Exception:
        db.rollback()
        log.exception("Simulation failed")
        raise HTTPException(status_code=500, detail="The simulation failed unexpectedly. Your data was not changed - please try again.")


def _store(db: Session, user_id: int, result: dict, parent_id=None) -> dict:
    """Save a successful run. If saving fails, the simulation result is still returned (without feedback)."""
    if result.get("status") != "ok":
        return result
    try:
        result["scenario_id"] = scenario_store.save_run(db, user_id, result, parent_id).id
    except SQLAlchemyError:
        db.rollback()
        log.exception("Could not store scenario run")
        result["assumptions"] = result.get("assumptions", []) + [
            "This run could not be saved, so feedback is not available for it."]
    return result


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_question(payload: SimulatorRequest, db: Session = Depends(get_db)):
    get_user_or_404(db, payload.user_id)
    return whatif_pipeline.analyze(db, payload.user_id, payload.question)


@router.post("/run", response_model=RunResponse)
def run_simulation(payload: SimulatorRequest, db: Session = Depends(get_db)):
    get_user_or_404(db, payload.user_id)
    result = _store(db, payload.user_id, _run_safely(db, payload.user_id, payload.question))
    _log_run(db, payload.user_id, result, "scenario_run")
    return result


def _log_run(db: Session, user_id: int, result: dict, action: str):
    access_log.record(db, user_id, action, "scenario",
                      f"scenario #{result['scenario_id']}" if result.get("scenario_id") else result["status"])
    if result.get("recommendation"):
        access_log.record(db, user_id, "recommendation_generated", "recommendation",
                          f"scenario #{result.get('scenario_id')}")


@router.post("/rerun/{scenario_id}", response_model=RunResponse)
def rerun_scenario(scenario_id: int, payload: RerunRequest, db: Session = Depends(get_db)):
    get_user_or_404(db, payload.user_id)
    previous = scenario_store.get_run(db, payload.user_id, scenario_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Scenario not found, so it cannot be re-run. Ask the question again.")
    result = _run_safely(db, payload.user_id, previous.question)  # full recalculation with the current Twin
    result["rerun_of"] = previous.id
    if result["status"] == "ok":
        result["learning_effect"] = scenario_store.learning_effect(previous, result)
    result = _store(db, payload.user_id, result, parent_id=previous.id)
    _log_run(db, payload.user_id, result, "scenario_rerun")
    return result
