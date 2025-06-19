from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: Optional[str]
    role: str
    school_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

#since "Hello From: " is included
class UserListResponse(BaseModel):
    Hello_From: List[UserOut]

    class Config:
        fields = {"Hello_From": "Hello From:"}
