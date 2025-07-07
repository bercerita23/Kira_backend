from pydantic import BaseModel
from datetime import datetime

class UserBadgeBase(BaseModel):
    is_viewed: bool = False

class UserBadgeCreate(UserBadgeBase):
    user_id: str
    badge_id: str

class UserBadge(UserBadgeBase):
    user_id: str
    badge_id: str
    earned_at: datetime

    class Config:
        orm_mode = True
