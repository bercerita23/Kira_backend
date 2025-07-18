from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

class StudentCreate(BaseModel): 
    password: str
    first_name: str
    last_name: str
    username: str

class StudentUpdate(BaseModel):
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None

class PasswordResetWithUsername(BaseModel): 
    username: str = None
    new_password: str

class PasswordResetWithEmail(BaseModel): 
    code: str
    email: EmailStr = None
    new_password: str

class StudentOut(BaseModel):
    username: str
    first_name: str
    last_name: str
    created_at: datetime
    last_login_time: datetime
    deactivated: bool

class StudentDeactivateRequest(BaseModel):
    username: str

class StudentReactivateRequest(BaseModel):
    username: str
