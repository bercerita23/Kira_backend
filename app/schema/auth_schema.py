from typing import Optional

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """Bearer Access Token"""

    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """Payload for Bearer Access Token"""

    sub: Optional[int] = None


class UserRegister(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: Optional[str] = None

class Invitation(BaseModel):
    school_id: str
    email: EmailStr
    first_name: str
    last_name: str

class ResetPasswordRequest(BaseModel): 
    user_id: Optional[str]
    email: Optional[EmailStr]


# class ResetPasswordRequest(BaseModel):
#     email: EmailStr
#     new_password: str

class UserCreate(BaseModel):
    school_id: str
    email: EmailStr
    password: str
    first_name: str
    last_name: str

class LoginRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str