from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, func

from app.database import Base


class Feedback(Base):
    """What the user said about a recommendation, and what actually happened.

    rating            helpful | partially_helpful | not_helpful   (an opinion - never changes a trait)
    reasons           list of reason tags
    task_id           the task the actual outcome is about (NULL if not given or the task was deleted later)
    task_title / estimated_hours   copied from the scenario, so the feedback stays meaningful if the task changes
    actual_hours, completed, deadline_met, hours_late   the actual outcome (all optional)
    relevant_traits   Twin traits the scenario used
    interpretation    how TwinMate read the feedback (which observations it created and why / why not)
    """

    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scenario_id = Column(Integer, ForeignKey("scenario_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    recommended_plan_id = Column(String(5), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    task_title = Column(String(200), nullable=True)
    estimated_hours = Column(Float, nullable=True)
    rating = Column(String(20), nullable=False)
    reasons = Column(JSON, nullable=False, default=list)
    actual_hours = Column(Float, nullable=True)
    completed = Column(Boolean, nullable=True)
    deadline_met = Column(Boolean, nullable=True)
    hours_late = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)
    relevant_traits = Column(JSON, nullable=False, default=list)
    interpretation = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
