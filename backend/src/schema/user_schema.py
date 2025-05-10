from pydantic import BaseModel
from datetime import datetime

class UserBase(BaseModel):
    username: str
    role: str
    school_id: int

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
