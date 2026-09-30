from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from app.database import Base


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    priority = Column(String(10), nullable=False, default="medium")  # low | medium | high
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="goals")
    # Deleting a goal keeps its tasks; their goal_id is simply set to NULL.
    tasks = relationship("Task", back_populates="goal")
