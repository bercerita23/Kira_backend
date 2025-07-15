from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: Optional[str]
    school_id: Optional[int]

class UserListResponse(BaseModel):
    Hello_From: List[UserOut]

class UserBadgeOut(BaseModel):
    badge_id: str
    earned_at: datetime
    is_viewed: bool
    name: str
    description: str | None
    icon_url: str | None

class UserBadgesOut(BaseModel):
    badges: List[UserBadgeOut]

class PointsOut(BaseModel): 
    premium_points: int
    regular_points: int

class StreakOut(BaseModel): 
    current_streak: int
    longest_streak: int
    last_activity: datetime