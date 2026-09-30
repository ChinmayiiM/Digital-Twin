"""Phase 6 - Privacy & Data Control.

Every route here requires the X-User-Id header to match the user in the URL (sent automatically by the
frontend). There is no login in this MVP; see README 'Limitations'.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AccessLog, ScenarioRun
from app.routers.users import get_user_or_404
from app.schemas.privacy import (AccessLogItem, DataUsedResponse, ForgetRequest, ForgetResponse, LearningUpdate,
                                 PermissionUpdate, PrivacyResponse)
from app.services import access_log, permission_gate, privacy_service, scenario_store

router = APIRouter(prefix="/api/privacy", tags=["Privacy & Data Control"])
log = logging.getLogger("twinmate.privacy")


def _owner(user_id: int, db: Session, caller: str):
    permission_gate.require_same_user(user_id, caller)
    get_user_or_404(db, user_id)


def _state(db: Session, user_id: int, message=None) -> dict:
    row = permission_gate.get_or_create(db, user_id)
    _, reason = permission_gate.can_learn(row)
    return {
        "user_id": user_id,
        "permissions": permission_gate.as_dict(row),
        "permission_labels": {k: label for k, (_, label) in permission_gate.CATEGORIES.items()},
        "learning_paused": bool(row.learning_paused),
        "learning_message": reason or "TwinMate can learn from your feedback and outcomes.",
        "inventory": privacy_service.inventory(db, user_id),
        "message": message,
    }


@router.get("/{user_id}", response_model=PrivacyResponse)
def get_privacy(user_id: int, db: Session = Depends(get_db), caller: str = Depends(permission_gate.request_user_id)):
    _owner(user_id, db, caller)
    return _state(db, user_id)


@router.put("/{user_id}/permissions", response_model=PrivacyResponse)
def update_permissions(user_id: int, payload: PermissionUpdate, db: Session = Depends(get_db),
                       caller: str = Depends(permission_gate.request_user_id)):
    _owner(user_id, db, caller)
    row = permission_gate.get_or_create(db, user_id)
    changed = []
    for name, value in payload.model_dump(exclude_none=True).items():
        column = permission_gate.CATEGORIES[name][0]
        if getattr(row, column) != value:
            setattr(row, column, value)
            changed.append(f"{permission_gate.label(name)}: {'on' if value else 'off'}")
    if not changed:  # duplicate update -> nothing to do, nothing logged
        return _state(db, user_id, "No changes - the permissions were already set that way.")
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("Permission update failed")
        raise HTTPException(status_code=500, detail="Unable to update privacy settings. Nothing was changed.")
    access_log.record(db, user_id, "permission_changed", "permissions", "; ".join(changed))
    return _state(db, user_id, "Saved. " + "; ".join(changed) + ".")


@router.put("/{user_id}/learning", response_model=PrivacyResponse)
def update_learning(user_id: int, payload: LearningUpdate, db: Session = Depends(get_db),
                    caller: str = Depends(permission_gate.request_user_id)):
    _owner(user_id, db, caller)
    row = permission_gate.get_or_create(db, user_id)
    if row.learning_paused == payload.paused:
        return _state(db, user_id, "Learning is already paused." if payload.paused else "Learning is already on.")
    row.learning_paused = payload.paused
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=500, detail="Unable to update privacy settings. Nothing was changed.")
    access_log.record(db, user_id, "learning_paused" if payload.paused else "learning_resumed", "learning")
    return _state(db, user_id, "Learning paused." if payload.paused else "Learning resumed.")


@router.post("/{user_id}/forget", response_model=ForgetResponse)
def forget_data(user_id: int, payload: ForgetRequest, db: Session = Depends(get_db),
                caller: str = Depends(permission_gate.request_user_id)):
    _owner(user_id, db, caller)
    try:
        result = privacy_service.forget(db, user_id, payload.categories)
    except SQLAlchemyError:
        log.exception("Forget failed")
        raise HTTPException(status_code=500, detail="The data could not be forgotten. Nothing was removed - please try again.")
    access_log.record(db, user_id, "data_forgotten", "data", ", ".join(payload.categories))
    return result


@router.get("/{user_id}/data-used", response_model=DataUsedResponse)
def data_used(user_id: int, scenario_id: int = Query(None), db: Session = Depends(get_db),
              caller: str = Depends(permission_gate.request_user_id)):
    """What a recommendation was based on (the latest run, or the given scenario)."""
    _owner(user_id, db, caller)
    if scenario_id is not None:
        run = scenario_store.get_run(db, user_id, scenario_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Scenario not found.")
    else:
        run = (db.query(ScenarioRun).filter(ScenarioRun.user_id == user_id)
               .order_by(ScenarioRun.id.desc()).first())
    if run is None:
        return {"categories": [], "message": "No recommendation has been generated yet. Run a What-If scenario first."}
    categories = (run.summary or {}).get("data_used", [])
    access_log.record(db, user_id, "data_used_viewed", "scenario", f"scenario #{run.id}")
    return {"scenario_id": run.id, "question": run.question, "created_at": run.created_at, "categories": categories,
            "message": "" if categories else "This scenario was run before data-use tracking existed. Run it again."}


@router.get("/{user_id}/export")
def export_twin(user_id: int, db: Session = Depends(get_db), caller: str = Depends(permission_gate.request_user_id)):
    _owner(user_id, db, caller)
    data = privacy_service.export(db, user_id)
    access_log.record(db, user_id, "twin_exported", "export")
    filename = f"twinmate-export-{data['generated_at'][:10]}.json"
    return JSONResponse(content=data, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{user_id}/access-logs", response_model=list[AccessLogItem])
def access_logs(user_id: int, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db),
                caller: str = Depends(permission_gate.request_user_id)):
    _owner(user_id, db, caller)
    rows = (db.query(AccessLog).filter(AccessLog.user_id == user_id)
            .order_by(AccessLog.id.desc()).limit(limit).all())
    return [{"id": r.id, "action": r.action, "text": access_log.ACTION_TEXT.get(r.action, r.action),
             "resource": r.resource, "detail": r.detail, "created_at": r.created_at} for r in rows]
