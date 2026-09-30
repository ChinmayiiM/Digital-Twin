from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import WorkingTime


class PreferenceCreate(BaseModel):
    """Body for POST/PUT /api/preferences/{user_id} (the user id comes from the URL)."""

    available_hours_per_day: float = Field(gt=0, le=24)
    preferred_working_time: WorkingTime


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    available_hours_per_day: float
    preferred_working_time: str
