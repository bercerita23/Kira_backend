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
from app.model.verification_codes import VerificationCode
from app.model.employee_codes import EmployeeCode
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
    # Token creation based on role
    role = None
    if user.is_super_admin:
        role = "super_admin"
    elif user.is_admin:
        role = "admin"
    elif (not user.is_super_admin) and (not user.is_admin):
        role = "student"

    

    access_token = create_access_token(
        subject=user.user_id,
        email=user.email,
        first_name=user.first_name,
        role=role,
        school_id=user.school_id,
        expires_delta=access_token_expires
    )
    user.last_login_time = datetime.now()
    db.commit()
    
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
    result = db.query(VerificationCode).filter(
        VerificationCode.email == request.email).first()
    
    if result: 
        temp = db.execute(
        text("DELETE FROM verification_codes WHERE email = :email"),
        {"email": request.email}
    )
    db.commit()
    
    # generate a 8 digit code and store it in the database with email & expiration time of 10 minutes
    code = str(uuid4())[:8]
    expires_at = datetime.now() + timedelta(minutes=20)

    entry = VerificationCode(
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
    
    result = db.query(VerificationCode).filter(
        VerificationCode.email == request.email).first()
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

    entry = VerificationCode(
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
        text("SELECT * FROM verification_codes WHERE email = :email"),
        {"email": email}

    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    if result.expires_at < datetime.now(): 
        raise HTTPException(status_code=400, detail="Expired verification code")
    
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
        text("DELETE FROM verification_codes WHERE email = :email"),
        {"email": email}
    )
    db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    return {"message": "Verification code deleted successfully"}


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(request: UserCreateWithCode, db: Session = Depends(get_db)):
    """_summary_: Register a new user with email verification code.(possibly employee_code)
    1. check if the email already exists, if so raise an exception
    2. check the verification code, if not found raise an exception if the code is expired raise an exception
    3. codes valid, process to register the user base on the employee_code
    Args:
        request (UserCreateWithCode): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    # check if the email already exists
    existing_user = db.query(User).filter(User.email == request.email).first()    
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    
    # if trying to register as an admin or super admin
    new_user = None
    if request.employee_code:
        temp = db.query(EmployeeCode).filter(
            EmployeeCode.code == request.employee_code).first()
        
        if temp.is_super_admin: # super admin
            new_user = User(
                user_id = generate_unique_user_id(db),
                school_id = None,
                email=request.email,
                hashed_password=get_password_hash(request.password),
                first_name=request.first_name,
                last_name=request.last_name,
                is_super_admin=True

            )
            
        if not temp.is_super_admin: # school admin
            new_user = User(
                user_id = generate_unique_user_id(db),
                email=request.email,
                school_id=request.school_id,
                hashed_password=get_password_hash(request.password),
                first_name=request.first_name,
                last_name=request.last_name,
                is_admin=True
            )
    
    else: # student
        new_user = User(
            user_id = generate_unique_user_id(db),
            school_id = request.school_id,
            email=request.email,
            hashed_password=get_password_hash(request.password),
            first_name=request.first_name,
            last_name=request.last_name,
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

    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password 


    db.commit()

    return {"message": "Password reset successfully"}