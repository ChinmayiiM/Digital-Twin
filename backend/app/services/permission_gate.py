"""Permission Gate (Phase 6): every Twin/simulator calculation asks here first what it may use.

    Request -> permission check -> allowed data only -> Twin / Simulator

The backend is the source of truth; the frontend switches only call these APIs.
"""
from typing import Dict

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.models import Permission

# API name -> (database column, label shown to the user)
CATEGORIES = {
    "timetable": ("allow_timetable", "Timetable & Available Hours"),
    "goals": ("allow_goals", "Goals"),
    "tasks": ("allow_tasks", "Tasks & Deadlines"),
    "history": ("allow_history", "Study / Work History"),
    "preferences": ("allow_preferences", "Preferences"),
    "behavior": ("allow_behavior", "Behavioral Patterns"),
}


class PermissionDenied(Exception):
    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def get_or_create(db: Session, user_id: int) -> Permission:
    """Users from earlier phases have no row yet: they get one with everything ON (unchanged behavior)."""
    row = db.query(Permission).filter(Permission.user_id == user_id).first()
    if row is None:
        row = Permission(user_id=user_id, allow_timetable=True, allow_goals=True, allow_tasks=True,
                         allow_history=True, allow_preferences=True, allow_behavior=True, learning_paused=False)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def as_dict(row: Permission) -> Dict[str, bool]:
    return {name: bool(getattr(row, column)) for name, (column, _) in CATEGORIES.items()}


def label(category: str) -> str:
    return CATEGORIES[category][1]


def can_learn(row: Permission) -> tuple:
    """(allowed, reason). Learning = new activity may change Twin traits."""
    if row.learning_paused:
        return False, ("Learning is paused. Your existing Twin is still available, but new activity will not "
                       "update your behavioral traits until learning is resumed.")
    if not row.allow_history:
        return False, ("The 'Study / Work History' permission is off, so TwinMate does not collect or analyze "
                       "new activity.")
    return True, ""


def require_learning(row: Permission):
    allowed, reason = can_learn(row)
    if not allowed:
        raise PermissionDenied(reason, 409 if row.learning_paused else 403)


def require_history(row: Permission):
    if not row.allow_history:
        raise PermissionDenied("The 'Study / Work History' permission is off, so new observations are not stored. "
                               "Turn it on in Privacy & Data.")


def enforce_history(db: Session, user_id: int):
    """For API routes that store new observations: HTTP 403 while 'Study / Work History' is off."""
    try:
        require_history(get_or_create(db, user_id))
    except PermissionDenied as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


def request_user_id(x_user_id: str = Header(default="", alias="X-User-Id")) -> str:
    """The frontend sends the current user's id in the X-User-Id header on every request."""
    return x_user_id.strip()


def require_same_user(user_id: int, header_value: str):
    """Ownership check for sensitive privacy endpoints (export, forget, permissions, logs).
    NOTE: there is no login in this hackathon MVP - this stops accidental or casual cross-user access,
    it is not real authentication (see README 'Limitations')."""
    if header_value != str(user_id):
        raise HTTPException(status_code=403, detail="You can only access your own data.")


def check_owner(owner_id: int, header_value: str):
    """For task/goal changes: if the caller identifies itself, it must be the owner."""
    if header_value and header_value != str(owner_id):
        raise HTTPException(status_code=403, detail="You can only change your own data.")
