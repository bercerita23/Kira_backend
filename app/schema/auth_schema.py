from typing import Optional

from pydantic import BaseModel, EmailStr


class Token(BaseModel):
    """Bearer Access Token"""

    access_token: str
    token_type: str


class TokenPayload(BaseModel):
    """Payload for Bearer Access Token"""

    sub: Optional[str] = None


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

class LoginRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str