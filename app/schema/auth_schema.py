from typing import Optional

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """Bearer Access Token"""

    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """Payload for Bearer Access Token"""
    sub: str  # usually user id
    email: Optional[EmailStr] = None
    first_name: str
    role: str
    school_id: Optional[str] = None
    exp: int
    iat: int


class UserRegister(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: Optional[str] = None

class ResetPasswordRequest(BaseModel): 
    username: Optional[str] = None
    email: Optional[str] = None


class AdminCreate(BaseModel):
    email: EmailStr
    school_id: str
    first_name: str
    last_name: str
    code: str
    password: str

class LoginRequestStudent(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    school_id: str
    password: str

class LoginRequestAdmin(BaseModel):
    email: str
    password: str