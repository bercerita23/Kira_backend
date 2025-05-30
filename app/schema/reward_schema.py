from pydantic import BaseModel
from datetime import datetime

class RewardBase(BaseModel):
    user_id: int
    type: str
    value: int

class RewardCreate(RewardBase):
    pass

class RewardResponse(RewardBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
