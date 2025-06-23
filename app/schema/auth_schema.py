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

class VerificationRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class UserCreateWithCode(BaseModel):
    # user_id
    employee_code:Optional[str] = None
    school_id: str
    email: EmailStr
    hashed_password: str
    first_name: str
    last_name: str
    password: str
    code: str

class LoginRequest(BaseModel):
    user_id: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str