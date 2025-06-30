from typing import Optional

from pydantic import BaseModel, EmailStr

class StudentCreate(BaseModel): 
    password: str
    first_name: str
    last_name: str
    username: str

class PasswordResetWithUsername(BaseModel): 
    username: str = None
    new_password: str

class PasswordResetWithEmail(BaseModel): 
    email: EmailStr = None
    new_password: str

