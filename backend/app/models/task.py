from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    estimated_hours = Column(Float, nullable=False)
    # Stored as a naive local date-time (no timezone), e.g. 2026-10-01 18:00:00
    deadline = Column(DateTime, nullable=True)
    priority = Column(String(10), nullable=False, default="medium")  # low | medium | high
    status = Column(String(20), nullable=False, default="pending")  # pending | in_progress | completed
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="tasks")
    goal = relationship("Goal", back_populates="tasks")
