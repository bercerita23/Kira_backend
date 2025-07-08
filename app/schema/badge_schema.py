from pydantic import BaseModel
from datetime import datetime

class BadgeBase(BaseModel):
    name: str
    description: str | None = None
    icon_url: str | None = None

class BadgeCreate(BadgeBase):
    badge_id: str

class Badge(BadgeBase):
    badge_id: str
    created_at: datetime

    class Config:
        orm_mode = True
