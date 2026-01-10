from datetime import timedelta, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.router.auth_util import *
from app.config import settings
from app.database import get_db
from app.schema.admin_schema import *
from app.schema.auth_schema import *
from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.temp_admins import TempAdmin
from app.router.dependencies import *
from app.router.aws_ses import *
from app.model.schools import School
from uuid import uuid4
from app.model.schools import SchoolStatus
from app.router.service.auth_service.login_service import (
    login_student_logic,
    login_administrator_logic,
)
from app.router.service.auth_service.register_service import (
    register_admin_logic,
    resend_verification_logic,
    get_all_school_logic,
)
from app.router.service.auth_service.password_service import (
    request_reset_password_logic,
    reset_admin_password_logic,
)


router = APIRouter()

@router.post("/login-stu", response_model=Token, status_code=status.HTTP_200_OK)
async def login_student(request: LoginRequestStudent, db: Session = Depends(get_db)):
    """Student login endpoint (delegates to service)."""
    return login_student_logic(db=db, request=request)
        

@router.post("/login-ada", response_model=Token, status_code=status.HTTP_200_OK)
async def login_administrator(request: LoginRequestAdmin, db: Session = Depends(get_db)):
    """Administrator login endpoint (delegates to service)."""
    return login_administrator_logic(db=db, request=request)


@router.post("/register-admin", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(request: AdminCreate, db: Session = Depends(get_db)):
    """Register a new admin (delegates to register service)."""
    return register_admin_logic(db=db, request=request)


@router.post("/request-reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def request_reset_password(request_body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Request reset password (delegates to password service)."""
    return request_reset_password_logic(db=db, request_body=request_body)
        

@router.post("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_admin_password(request: PasswordResetWithEmail, db: Session = Depends(get_db)):
    """Reset admin password (delegates to password service)."""
    return reset_admin_password_logic(db=db, request=request)


@router.get("/school", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_school(db: Session = Depends(get_db)):
    """Get all active schools (delegates to register service)."""
    return get_all_school_logic(db=db)


@router.post("/resend-verification", response_model=dict, status_code=status.HTTP_200_OK)
async def resend_verification_code(request: ResendVerificationEmail, db: Session = Depends(get_db)):
    """Resend verification code (delegates to register service)."""
    return resend_verification_logic(db=db, request=request)