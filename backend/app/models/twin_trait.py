from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from app.database import Base

# Order in which traits are stored and shown.
TRAIT_ORDER = [
    "productivity_morning",
    "productivity_afternoon",
    "productivity_evening",
    "task_estimation",
    "focus_capacity",
    "task_ordering",
    "procrastination",
]

TRAIT_LABELS = {
    "productivity_morning": "Morning productivity",
    "productivity_afternoon": "Afternoon productivity",
    "productivity_evening": "Evening productivity",
    "task_estimation": "Task estimation",
    "focus_capacity": "Focus capacity",
    "task_ordering": "Preferred task ordering",
    "procrastination": "Procrastination tendency",
}


class TwinTrait(Base):
    """A learned behavioral trait: value + confidence + evidence.

    trait_value          number the Pattern Analyzer calculated; NULL while there is not enough evidence
    display_value        the same value as human-readable text (or "Not enough evidence yet")
    confidence           0..1, "how much evidence do we have" (not statistical certainty)
    evidence_count       how many observations were used
    sufficient_evidence  False -> the UI must not present a value
    description          plain-language "why TwinMate thinks this", built from the stored evidence
    details              extra numbers behind the value (means, counts, alpha ...)
    """

    __tablename__ = "twin_traits"
    __table_args__ = (UniqueConstraint("user_id", "trait_name", name="uq_user_trait"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trait_name = Column(String(50), nullable=False)
    trait_value = Column(Float, nullable=True)
    display_value = Column(String(200), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    evidence_count = Column(Integer, nullable=False, default=0)
    sufficient_evidence = Column(Boolean, nullable=False, default=False)
    description = Column(Text, nullable=False, default="")
    details = Column(JSON, nullable=False, default=dict)
    last_updated = Column(DateTime, server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="twin_traits")

    @property
    def display_name(self) -> str:
        return TRAIT_LABELS.get(self.trait_name, self.trait_name)
