from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class TwinTraitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    trait_name: str
    display_name: str
    trait_value: Optional[float] = None
    display_value: str
    confidence: float
    evidence_count: int
    sufficient_evidence: bool
    description: str
    details: Dict[str, Any]
    last_updated: datetime


class TwinConfig(BaseModel):
    alpha: float
    minimum_evidence: int
    full_confidence_at: int


class StatedPreference(BaseModel):
    """What the user SAID (Phase 2 profile) - kept separate from observed behavior."""

    available_hours_per_day: float
    preferred_working_time: str


class TwinResponse(BaseModel):
    user_id: int
    analyzed: bool
    last_analyzed: Optional[datetime] = None
    total_observations: int
    demo_observations: int
    observations_pending_analysis: int
    stated_preference: Optional[StatedPreference] = None
    config: TwinConfig
    traits: List[TwinTraitResponse]
