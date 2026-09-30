from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text, func

from app.database import Base


class ScenarioRun(Base):
    """One successful What-If simulation (Phase 4 result), stored so feedback can point at it (Phase 5).

    summary   the key calculated numbers of that run (plans, on-time chances, adjusted hours, Twin values used).
              Used to compare a re-run with the original - the simulation itself is always recalculated.
    parent_id set when this run is a re-run of an earlier scenario (same question, updated Twin)
    """

    __tablename__ = "scenario_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("scenario_runs.id", ondelete="SET NULL"), nullable=True)
    question = Column(Text, nullable=False)
    recommended_plan_id = Column(String(5), nullable=True)
    summary = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
