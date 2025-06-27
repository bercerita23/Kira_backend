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
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str