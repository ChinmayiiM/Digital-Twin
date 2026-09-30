from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.common import PersonName


class UserCreate(BaseModel):
    name: PersonName


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
