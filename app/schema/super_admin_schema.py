from typing import Optional

from pydantic import BaseModel, EmailStr

class Invitation(BaseModel):
    school_id: str
    email: EmailStr
    first_name: str
    last_name: str