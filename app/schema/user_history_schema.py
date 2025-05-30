from pydantic import BaseModel
from datetime import datetime

class UserHistoryBase(BaseModel):
    user_id: int
    quiz_id: int
    score: int
    attempt_date: datetime

class UserHistoryCreate(UserHistoryBase):
    pass

class UserHistoryResponse(UserHistoryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
