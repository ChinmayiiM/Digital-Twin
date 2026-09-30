from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from app.database import Base


class BehaviorObservation(Base):
    """One piece of evidence about how the user actually behaves.

    observation_type  what was observed (working_time, task_estimation, task_order, delay, focus_session)
    observed_value    the main number (meaning depends on the type - see schemas/behavior_observation.py)
    context           extra structured details, e.g. {"estimated_hours": 2.0}
    source            who/what produced it: user | task_activity | system | demo (synthetic)
    """

    __tablename__ = "behavior_observations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    observation_type = Column(String(30), nullable=False, index=True)
    observed_value = Column(Float, nullable=False)
    context = Column(JSON, nullable=False, default=dict)
    source = Column(String(20), nullable=False, default="user")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="observations")
