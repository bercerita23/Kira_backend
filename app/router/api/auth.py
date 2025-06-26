from datetime import timedelta, datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.router.auth_util import *
from app.config import settings
from app.database import get_db
from app.schema.auth_schema import *
from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.employee_codes import EmployeeCode
from app.router.dependencies import *
from app.router.aws_ses import *
from uuid import uuid4


router = APIRouter()

@router.post("/login-stu", response_model=Token, status_code=status.HTTP_200_OK)
async def login_student(request: LoginRequest, db: Session = Depends(get_db)):
    """_summary_

    Args:
        request (LoginRequest): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_
        HTTPException: _description_
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    user = None

    # Try to fetch user based on provided identifiers
    if request.user_id:
        user = db.query(User).filter(User.user_id  == request.user_id).first()
    elif request.email:
        user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect credentials"
        )

   
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        subject=user.user_id,
        email=user.email,
        first_name=user.first_name,
        role="student",
        school_id=user.school_id,
        expires_delta=access_token_expires
    )
    user.last_login_time = datetime.now()
    db.commit()
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login-ada", response_model=Token, status_code=status.HTTP_200_OK)
async def login_administrator(request: LoginRequest, db: Session = Depends(get_db)):
    """_summary_

    Args:
        request (LoginRequest): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_
        HTTPException: _description_
        HTTPException: _description_

    Returns:
        _type_: _description_
    """

    user = None

    # Try to fetch user based on provided identifiers
    if request.user_id:
        user = db.query(User).filter(User.user_id  == request.user_id).first()
    elif request.email:
        user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User not found"
        )
    
    if not user.is_admin and not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You're a student, you don't have admin accesss"
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect credentials"
        )

    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # Token creation based on role
    role = None
    school_id = None
    if user.is_super_admin:
        role = "super_admin"
    else:
        role = "admin"
        school_id = user.school_id
    
    access_token = create_access_token(
        subject=user.user_id,
        email=user.email,
        first_name=user.first_name,
        role=role,
        school_id=school_id,
        expires_delta=access_token_expires
    )
    user.last_login_time = datetime.now()
    db.commit()
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.patch("/register-admin", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(request: UserCreate, db: Session = Depends(get_db)):
    """_summary_: Register a new user after check the information user and suepr admin entered when inviting a new school admin.
    

    Args:
        request (UserCreateWithCode): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    
    existing_user = db.query(User).filter(User.email == request.email).first()

    if existing_user:
        # Update existing user
        existing_user.hashed_password = get_password_hash(request.password)
        db.commit()
        db.refresh(existing_user)
        return {"message": "User information updated successfully"}
    else: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User not found.")

@router.post("/request-reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def request_reset_password(request_body: ResetPasswordRequest, db: Session = Depends(get_db)):
    """_summary_: this router will be called by the student or the admin to send a reset password email to the admin. 
    1. check who's sending the request by checking the content of the request.
    1.1. if it's an email -> an admin is trying to send the request 
    1.2. if it's an user_id -> a student is trying to send the request 

    2. ADMIN: send a reset password email to the admin with a verification code and store it in the database

    3. STUDENT: send a reset password request to the admin with a verification code and store it in the database
    Args:
        email (str): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """

    if request_body.email: # Admin is trying to reset password
        user = db.query(User).filter(User.email == request_body.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        code = str(uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=180)
        
        reset_code_entry = VerificationCode(
            email=user.email,
            code=code,
            expires_at=expires_at
        )
        db.add(reset_code_entry)
        db.commit()
        
        # send the reset password email to the admin
        send_admin_verification_email(user.email, "forgot-password", code, user.first_name)
        
        return {"message": f"Reset password email sent to {user.email}"}
    
    else: # Student is trying to reset password
        student = db.query(User).filter(User.user_id == request_body.user_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="User not found")   
        
        admin = db.query(User).filter(User.school_id == student.school_id, User.is_admin == True).first()
        # send the reset password request to the admin's email
        send_reset_request_to_admin(admin.email, "admin/login", code, 
                                student.user_id, student.school_id, student.first_name)
        

        return {"message": f"Reset password email sent to {admin.email}"}
        
    