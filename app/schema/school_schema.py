from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class SchoolBase(BaseModel):
    name: str
    location: Optional[str] = None

class SchoolCreate(SchoolBase):
    pass

class SchoolResponse(SchoolBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
