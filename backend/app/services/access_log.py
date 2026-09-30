"""Access log (Phase 6): records important data events for the 'Recent Data Activity' list.

Only short, non-sensitive text is stored (no task titles, no values, no secrets).
Logging never breaks the real operation: if writing the log fails, it is skipped.
"""
import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import AccessLog
from app.services.pattern_analyzer import utc_now

log = logging.getLogger("twinmate.access")

ACTION_TEXT = {
    "twin_viewed": "Viewed Digital Twin",
    "scenario_run": "Ran What-If scenario",
    "recommendation_generated": "Recommendation generated",
    "scenario_rerun": "Re-ran What-If scenario",
    "feedback_submitted": "Submitted feedback",
    "twin_updated": "Twin updated",
    "permission_changed": "Changed data permissions",
    "learning_paused": "Paused learning",
    "learning_resumed": "Resumed learning",
    "data_forgotten": "Forgot data",
    "data_used_viewed": "Viewed data used",
    "twin_exported": "Exported Twin",
}
REPEAT_WINDOW = timedelta(seconds=60)  # views repeated within a minute are logged once (page refreshes)


def record(db: Session, user_id: int, action: str, resource: str, detail: str = "", dedupe: bool = False):
    try:
        if dedupe:
            recent = (db.query(AccessLog)
                      .filter(AccessLog.user_id == user_id, AccessLog.action == action,
                              AccessLog.created_at >= utc_now() - REPEAT_WINDOW).first())
            if recent:
                return
        db.add(AccessLog(user_id=user_id, action=action, resource=resource, detail=detail[:200],
                         created_at=utc_now()))
        db.commit()
    except Exception:  # never let logging break the user's action
        db.rollback()
        log.exception("Could not write access log")
