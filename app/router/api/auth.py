from datetime import timedelta, datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.auth_util import *
from app.config import settings
from app.database import get_db
from app.schema.auth_schema import LoginRequest, ResetPasswordRequest, VerificationRequest, Token, UserCreateWithCode, UserRegister
from app.model.users import User
from app.model.verification_codes import VerificationCodes
from app.router.dependencies import *
from app.router.aws_ses import send_verification_email
from uuid import uuid4


router = APIRouter()


@router.post("/login", response_model=Token, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """
    Flexible login: accepts user_id and/or email along with password.
    """

    user = None

    # Try to fetch user based on provided identifiers
    if request.user_id:
        user = db.query(User).filter(User.user_id  == request.user_id).first()

    if not user and request.email:
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

    # Token creation based on role
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    if user.is_super_admin:
        role = "super_admin"
    elif user.is_admin:
        role = "admin"
    else:
        role = "student"

    access_token = create_access_token(
        subject=user.user_id,
        email=user.email,
        first_name=user.first_name,
        role=role,
        school_id=user.school_id,
        expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}



@router.post("/request-email-register", response_model=dict, status_code=status.HTTP_200_OK)
async def request_email_verification(
    request: VerificationRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """_summary_: Frontend will call this endpoint to request a verification code for email verification. 
    1. Generate an 8-digit code and store it in the database with email & expiration time of 10 minutes.
    2. Send the code to the email address provided in the request with SES.

    Args:
        email (EmailRequest): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    result = db.query(VerificationCodes).filter(
        VerificationCodes.email == request.email).first()
    temp = None
    if result: 
        temp = db.execute(
        text("DELETE FROM verification_code WHERE email = :email"),
        {"email": request.email}
    )
    db.commit()
    if temp.rowcount == 0:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    
    # generate a 8 digit code and store it in the database with email & expiration time of 10 minutes
    code = str(uuid4())[:8]
    expires_at = datetime.now() + timedelta(minutes=10)

    entry = VerificationCodes(
        email=request.email,
        code=code,
        expires_at=expires_at)
    
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    send_verification_email(request.email, code)
    return {"message": f"Verification code was sent to {request.email}"}


@router.post("/request-email-pw-reset", response_model=dict, status_code=status.HTTP_200_OK)
async def request_email_verification(
    request: VerificationRequest, db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """_summary_: Frontend will call this endpoint to request a verification code for email verification. 
    1. If the email exists in the database, proceed to step 2, if not raise an exception.
    2. Generate an 8-digit code and store it in the database with email & expiration time of 10 minutes.
    3. Send the code to the email address provided in the request with SES.

    Args:
        email (EmailRequest): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    # fetch user by email
    user = db.query(User).filter(
        User.email == request.email).first()
    # if user is not found or password is incorrect, raise an exception
    if not user:
        raise HTTPException(
           status_code=status.HTTP_400_BAD_REQUEST,
           detail="Email was not registered. Please register first.",
        )  
    
    result = db.query(VerificationCodes).filter(
        VerificationCodes.email == request.email).first()
    temp = None
    if result: 
        temp = db.execute(
        text("DELETE FROM verification_code WHERE email = :email"),
        {"email": request.email}
    )
    db.commit()
    if temp.rowcount == 0:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    
    # generate a 8 digit code and store it in the database with email & expiration time of 10 minutes
    code = str(uuid4())[:8]
    expires_at = datetime.now() + timedelta(minutes=10)

    entry = VerificationCodes(
        email=request.email,
        code=code,
        expires_at=expires_at)
    
    db.add(entry)
    db.commit()
    db.refresh(entry)
    
    send_verification_email(request.email, code)
    return {"message": f"Verification code was sent to {request.email}"}
    

@router.get("/code", response_model=dict, status_code=status.HTTP_200_OK)
async def get_verification_code(email: str = Query(...), db: Session = Depends(get_db)):
    """_summary_

    Args:
        email (str, optional): _description_. Defaults to Query(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """

    result = db.execute(
        text("SELECT * FROM verification_code WHERE email = :email"),
        {"email": email}

    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    return {"email": result.email,"code": result.code,"expires_at": result.expires_at.isoformat()}

@router.delete("/code", status_code=status.HTTP_204_NO_CONTENT)
async def delete_verification_code(email: str = Query(...), db: Session = Depends(get_db)):
    """_summary_

    Args:
        email (str, optional): _description_. Defaults to Query(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    # Delete verification code entry from verification_code table
    # Return verification entry by email from verification_code table
    result = db.execute(
        text("DELETE FROM verification_code WHERE email = :email"),
        {"email": email}
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    return {"message": "Verification code deleted successfully"}


@router.post("/register", response_model=dict, status_code=status.HTTP_200_OK)
async def register(request: UserCreateWithCode, db: Session = Depends(get_db)):
    code = db.execute(
        text("SELECT * FROM verification_code WHERE email = :email AND code = :code"),
        {"email": request.email, "code": request.code}
    ).fetchone()

    if not code :
        raise HTTPException(status_code=400, detail="Verification code is incorrect")
    if code.expires_at < datetime.now():
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    db.execute(text("DELETE FROM verification_code WHERE email = :email"), {"email": request.email})

    hashed_password = get_password_hash(request.password)

    # always 'stu' for now
    new_user = User(
        email=request.email,
        password=hashed_password,
        first_name=request.first_name,
        last_name=request.last_name,
        role="stu",
        school_id=None  # If you later implement school check you can fill this
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User registered successfully"}

@router.post("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """_summary_ : 
    1. if the email and the verification code match, proceed to step 2, if not raise an exception
    2. check if the code is expired
    2. if valid reset the password
    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_ a message in JSON format indicating success with 200
    """
    # Logic for resetting password goes here

    record = db.query(VerificationCodes).filter(
        VerificationCodes.email == request.email,
        VerificationCodes.code == request.code
    ).first()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    if record.expires_at < datetime.now(): 
        raise HTTPException(status_code=400, detail="Expired verification code")

    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password 

    db.delete(record)
    db.commit()

    return {"message": "Password reset successfully"}