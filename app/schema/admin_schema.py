from typing import Optional

from pydantic import BaseModel, EmailStr

class StudentCreate(BaseModel): 
    email: Optional[EmailStr] = None
    password: str
    first_name: str
    last_name: str
    phone_number: Optional[str] = None

class PasswordReset(BaseModel): 
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    new_password: str

