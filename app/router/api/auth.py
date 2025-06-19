from datetime import timedelta, datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from app import auth_util
from app.config import settings
from app.database import get_db
from app.schema.auth_schema import Token, UserRegister
from app.model.user_model import User
from app.router.dependencies import *
from app.router.aws_ses import send_verification_email
from uuid import uuid4


router = APIRouter()

# NEED TO BE COMMENTED OUT IN PRODUCTION
@router.get("/db")
def test_db(db: Session = Depends(get_db)):
    res = db.query(User).filter(User.email.isnot(None)).all()
    return {
        "Hello From: ": res
    }


@router.post("/login", response_model=Token)
def login_for_access_token(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
) -> Dict[str, Any]:
    """_summary_ login a user and return an access token w/ valid credentials. 

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        form_data (OAuth2PasswordRequestForm, optional): _description_. Defaults to Depends().

    Raises:
        HTTPException: _description_

    Returns:
        Dict[str, Any]: _description_
    """

    # fetch user by email
    user = db.query(User).filter(
        User.email == form_data.username).first()

    # if user is not found or password is incorrect, raise an exception
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect Credentials",
        )
    if not auth_util.verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect Credentials",
        )

    # access token creation
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth_util.create_access_token(
        subject=user.id, email=user.email, first_name=user.first_name, role=user.role, school_id=user.school_id, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=dict, status_code=status.HTTP_200_OK)
def register(user_register: UserRegister, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_register.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")

    code = str(uuid4())[:8]
    expires_at = datetime.now() + timedelta(minutes=10)

    db.execute(
        text("INSERT INTO verification_code (email, code, expires_at) VALUES (:email, :code, :expires_at) ON CONFLICT (email) DO UPDATE SET code = :code, expires_at = :expires_at"),
        {"email": user_register.email, "code": code, "expires_at": expires_at}
    )
    db.commit()

    send_verification_email(user_register.email, code)

    return {"message": "Verification code sent to email"}
    
@router.post("/verify-email", response_model=dict)
def verify_email(code: str, user_register: UserRegister, db: Session = Depends(get_db)):
    record = db.execute(
        text("SELECT * FROM verification_code WHERE email = :email"),
        {"email": user_register.email}
    ).fetchone()

    if not record or record.code != code or record.expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="Invalid or expired code")

    # Delete verification entry
    db.execute(text("DELETE FROM verification_code WHERE email = :email"), {"email": user_register.email})

    # Hash and save user
    hashed_password = auth_util.get_password_hash(user_register.password)
    user_register.password = hashed_password
    new_user = User(**user_register.model_dump())
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User verified and created successfully"}


@router.post("/reset-pw-req", response_model=dict , status_code=status.HTTP_200_OK)
def reset_password_request(email: str, db: Session = Depends(get_db)):
    """_summary_ request a password reset for the user with the given email.

    Args:
        email (str): _description_ the email of the user requesting a password reset
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (user_model.User, optional): _description_. Defaults to Depends(auth_util.get_current_user).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_ a message in JSON format indicating success with 200
    """
    # Logic for sending reset password email goes here
    return {"message": "Password reset request sent successfully"}


@router.post("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
def reset_password():
    """_summary_ reset the password for the user with the given email.

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_ a message in JSON format indicating success with 200
    """
    # Logic for resetting password goes here
    return {"message": "Password reset successfully"}