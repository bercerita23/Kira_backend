from pydantic import BaseModel
from datetime import datetime

class StreakBase(BaseModel):
    current_streak: int
    longest_streak: int
    last_activity: datetime | None = None

class StreakCreate(StreakBase):
    user_id: str

class Streak(StreakBase):
    user_id: str
    updated_at: datetime

    class Config:
        orm_mode = True
