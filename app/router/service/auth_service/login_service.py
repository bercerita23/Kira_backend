from datetime import timedelta, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.config import settings
from app.router.auth_util import verify_password, create_access_token
from app.model.users import User


def login_student_logic(db: Session, request) -> dict:
    # Validate that either username or email is provided
    if not request.username and not request.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either username or email must be provided"
        )
    # Validate that school_id is provided
    if not request.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="School ID is required"
        )

    # Find user by username or email
    user = None
    if request.username:
        user = db.query(User).filter(User.username == request.username).first()
    else:
        user = db.query(User).filter(User.email == request.email).first()

    if user and user.deactivated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is deactivated"
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credentials."
        )
    if user.school_id != request.school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Student does not belong to the specified school"
        )

    if user.deactivated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is deactivated"
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credentials."
        )

    if (user.is_admin or user.is_super_admin):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Access denied — admin accounts cannot log in as students"
        )

    # Set school_id based on role
    school_id = None if user.is_super_admin else user.school_id

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    access_token = create_access_token(
        subject=user.user_id,
        email=user.email,
        first_name=user.first_name,
        role="student",
        school_id=school_id,
        expires_delta=access_token_expires
    )

    # Update last login time
    user.last_login_time = datetime.now()
    db.commit()

    return {"access_token": access_token, "token_type": "bearer"}


def login_administrator_logic(db: Session, request) -> dict:
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Credentials"
        )

    if not user.is_admin and not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You're a student, you don't have admin accesss"
        )

    if user.deactivated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is deactivated"
        )

    # Only require school_id for non-super-admins
    if not user.is_super_admin:
        if not request.school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admins must select a school to login"
            )
        user_school_id = str(user.school_id).strip() if user.school_id else None
        req_school_id = str(request.school_id).strip() if request.school_id else None
        if user_school_id != req_school_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Admin does not belong to the specified school"
            )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Credentials"
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # Token creation based on role
    if user.is_super_admin:
        role = "super_admin"
        school_id = None
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
