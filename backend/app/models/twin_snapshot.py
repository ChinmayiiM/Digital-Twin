from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Text, func

from app.database import Base


class TwinSnapshot(Base):
    """The Twin BEFORE and AFTER one learning update (Phase 5 Twin Diff).

    traits_before / traits_after   {trait_name: {value, display, confidence, evidence_count, sufficient}}
    changes                        the calculated diff with a reason per changed trait
    """

    __tablename__ = "twin_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    feedback_id = Column(Integer, ForeignKey("feedback.id", ondelete="CASCADE"), nullable=True, index=True)
    reason = Column(Text, nullable=False, default="")
    traits_before = Column(JSON, nullable=False, default=dict)
    traits_after = Column(JSON, nullable=False, default=dict)
    changes = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
