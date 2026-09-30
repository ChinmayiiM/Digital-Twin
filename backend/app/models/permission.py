from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, func

from app.database import Base


class Permission(Base):
    """What TwinMate may USE for one user (Phase 6). One row per user, created with everything ON,
    so users from Phases 1-5 keep exactly the behavior they had.

    allow_timetable    available hours per day (capacity)
    allow_goals        goal titles (help recognise tasks in a what-if question)
    allow_tasks        tasks and their deadlines / estimates
    allow_history      collecting + analyzing study/work activity (behavioral observations)
    allow_preferences  stated preferences (preferred working time)
    allow_behavior     using the learned Twin traits in simulations and recommendations
    learning_paused    True -> no new activity changes the Twin (existing traits stay available)
    """

    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    allow_timetable = Column(Boolean, nullable=False, default=True)
    allow_goals = Column(Boolean, nullable=False, default=True)
    allow_tasks = Column(Boolean, nullable=False, default=True)
    allow_history = Column(Boolean, nullable=False, default=True)
    allow_preferences = Column(Boolean, nullable=False, default=True)
    allow_behavior = Column(Boolean, nullable=False, default=True)
    learning_paused = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
