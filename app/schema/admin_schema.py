from typing import Optional

from pydantic import BaseModel, EmailStr

class StudentCreate(BaseModel): 
    password: str
    first_name: str
    last_name: str

class PasswordResetWithId(BaseModel): 
    user_id: str = None
    new_password: str

class PasswordResetWithEmail(BaseModel): 
    email: EmailStr = None
    new_password: str

