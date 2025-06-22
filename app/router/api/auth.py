from datetime import timedelta, datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.auth_util import *
from app.config import settings
from app.database import get_db
from app.schema.auth_schema import ResetPasswordRequest, EmailRequest, Token, UserCreateWithCode, UserRegister
from app.model.users import User
from app.router.dependencies import *
from app.router.aws_ses import send_verification_email
from uuid import uuid4


router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
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
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect Credentials",
        )

    # access token creation
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.id, email=user.email, first_name=user.first_name, role=user.role, school_id=user.school_id, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# EMAIL VERIFICATION <--- cant the verification be done in one of the routes automatically?
@router.post("/request-email")
async def request_email_verification():
    # Generate verification code and expires_at
    # Store in verification_code table
    # Send code via email
    pass

@router.get("/code", response_model=dict, status_code=status.HTTP_200_OK)
async def get_verification_code(email: str = Query(...), db: Session = Depends(get_db)):
    result = db.execute(
        text("SELECT * FROM verification_code WHERE email = :email"),
        {"email": email}

    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    return {"email": result.email,"code": result.code,"expires_at": result.expires_at.isoformat()}

@router.delete("/code", status_code=status.HTTP_204_NO_CONTENT)
async def delete_verification_code(email: str = Query(...), db: Session = Depends(get_db)):
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
    """
    """
    code = db.execute(
        text("SELECT * FROM verification_code WHERE email = :email AND code = :code"),
        {"email": request.email, "code": request.code}
    ).fetchone()

    if not code :
        raise HTTPException(status_code=400, detail="Verification code is incorrect")
    if code.expired_at < datetime.now():
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
    
@router.post("/register-request", response_model=dict, status_code=status.HTTP_200_OK)
async def register_request(request: EmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # TODO: create domain col in school table
    # TODO: email domain belongs to allowed schools
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # domain = request.email.split('@')[-1]
    # school = db.query(School).filter(School.domain == domain).first()
    # if not school:
    #     raise HTTPException(status_code=400, detail="Email domain not recognized")

    # code generation
    code = str(uuid4())[:8]
    expires_at = datetime.now() + timedelta(minutes=10)

    db.execute(
        text("""
            INSERT INTO verification_code (email, code, expires_at)
            VALUES (:email, :code, :expires_at)
            ON CONFLICT (email) DO UPDATE SET code = :code, expires_at = :expires_at
        """),
        {"email": request.email, "code": code, "expires_at": expires_at}
    )
    db.commit()


    # TODO: change the method 
    send_verification_email(request.email, code)

    return {"message": "Verification code sent to email"}



@router.post("/reset-pw-request", response_model=dict , status_code=status.HTTP_200_OK)
async def reset_password_request(request: EmailRequest, db: Session = Depends(get_db)):
    """_summary_ : 
    1. if the email exists in the database, if yes proceed to step 2, if no raise an exception
    2. generate a 8 digit code and store it in the database with email & expiration time of 10 minutes
    3. send the code to the email address provided in the request with SES

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
    email = request.email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")

    code = str(uuid4())[:8]
    expires_at = datetime.now() + timedelta(minutes=10)

    db.execute(
        text("INSERT INTO verification_code (email, code, expires_at) VALUES (:email, :code, :expires_at) "
             "ON CONFLICT (email) DO UPDATE SET code = :code, expires_at = :expires_at"),
        {"email": email, "code": code, "expires_at": expires_at}
    )
    db.commit()
    # change to the actual send email function 
    send_verification_email(email, code)

    
    return {"message": "Password reset request sent successfully"}


@router.post("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """_summary_ : 
    1. if the email and the verification code match, proceed to step 2, if not raise an exception
    2. update the user password
    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_ a message in JSON format indicating success with 200
    """
    # Logic for resetting password goes here

    record = db.execute(
        text("SELECT * FROM verification_code WHERE email = :email AND code = :code"),
        {"email": request.email, "code": request.code}
    ).fetchone()

    if not record:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    if record.expires_at < datetime.now(): 
        raise HTTPException(status_code=400, detail="Expired verification code")

    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    hashed_password = get_password_hash(request.new_password)
    user.password = hashed_password

    db.execute(
        text("DELETE FROM verification_code WHERE email = :email"),
        {"email": request.email}
    )
    db.commit()

    return {"message": "Password reset successfully"}