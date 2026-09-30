from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.database import Base


class Preference(Base):
    """The user's *stated* preferences. No learned traits are stored here."""

    __tablename__ = "preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    available_hours_per_day = Column(Float, nullable=False)
    preferred_working_time = Column(String(20), nullable=False)  # Morning | Afternoon | Evening | Flexible

    user = relationship("User", back_populates="preference")
