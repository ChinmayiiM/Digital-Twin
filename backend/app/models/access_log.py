from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.database import Base


class AccessLog(Base):
    """One important data event (Phase 6). Short, non-sensitive text only - never task contents or values."""

    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    action = Column(String(40), nullable=False)
    resource = Column(String(40), nullable=False)
    detail = Column(String(200), nullable=False, default="")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
