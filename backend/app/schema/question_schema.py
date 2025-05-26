from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class QuestionBase(BaseModel):
    quiz_id: int
    type: str
    content: str
    choices: Optional[str] = None
    correct_answer: str

class QuestionCreate(QuestionBase):
    pass

class QuestionResponse(QuestionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
