from pydantic import BaseModel
from datetime import datetime

class QuizBase(BaseModel):
    topic: str

class QuizCreate(QuizBase):
    pass

class QuizResponse(QuizBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
