from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: Optional[str]
    school_id: Optional[int]

    class Config:
        orm_mode = True

class UserListResponse(BaseModel):
    Hello_From: List[UserOut]

    class Config:
        fields = {"Hello_From": "Hello From:"}
