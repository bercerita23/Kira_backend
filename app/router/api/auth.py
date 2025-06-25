from datetime import timedelta, datetime
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.auth_util import *
from app.config import settings
from app.database import get_db
from app.schema.auth_schema import LoginRequest, ResetPasswordRequest, Invitation, Token, UserCreate, UserRegister
from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.employee_codes import EmployeeCode
from app.router.dependencies import *
from app.router.aws_ses import send_verification_email
from uuid import uuid4


router = APIRouter()

@router.post("/login-stu", response_model=Token, status_code=status.HTTP_200_OK)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
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
async def login(request: LoginRequest, db: Session = Depends(get_db)):
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



@router.post("/invite", response_model=dict, status_code=status.HTTP_200_OK)
async def request_email_verification(
    request: Invitation, db: Session = Depends(get_db) #TODO: add a dependency to get super admin user)
) -> Dict[str, Any]:
    """_summary_: Super admin will call this endpoint to sned an invitation email to a new school admin to register. 
    1. If the email exists in the DB, raise an exception. 
    2. Generate a verification code and store it in the database
    3. Temporarily store the user information in the users table to compare later
    4. Send the code to the email address provided in the request with SES.

    Args:
        request (Invitation): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    # step 1: Check if the email already exists in the database
    user = db.query(User).filter(User.email == request.email).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered. Please use a different email.",
        )

    # step 2: generate a verification code and store it in the database
    result = db.query(VerificationCode).filter(
        VerificationCode.email == request.email).first()
    if result: 
        temp = db.execute(
        text("DELETE FROM verification_codes WHERE email = :email"),
        {"email": request.email}
    )
    db.commit()
    # generate a 8 digit code and store it in the database with email & expiration time of 180 minutes
    code = str(uuid4())[:8]
    expires_at = datetime.now() + timedelta(minutes=180)
    entry = VerificationCode(
        email=request.email,
        code=code,
        expires_at=expires_at)
    db.add(entry)
    db.commit()
    db.refresh(entry)

    # step 3: Temporarily store the user information in the users table to compare later
    temp_user = User(
        user_id=generate_unique_user_id(db),
        school_id=request.school_id,
        email=request.email,
        first_name=request.first_name,
        last_name=request.last_name,
        hashed_password="",
        is_admin=True,  
    )
    db.add(temp_user)
    db.commit()
    db.refresh(temp_user)
    
    send_verification_email(temp_user.email, "signup", code, 
                            temp_user.user_id,
                            temp_user.school_id,
                            temp_user.first_name)
    return {"message": f"Verification code was sent to {request.email}"}

@router.get("/user-temp", response_model=dict, status_code=status.HTTP_200_OK)
async def check_user_info(email: str = Query(...), db: Session = Depends(get_db)):
    """_summary_ fetch the information that was entered by the admin when inviting a new school admin.

    Args:
        email (str, optional): _description_. Defaults to Query(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    user = db.query(User).filter(User.email == email).first()
    if not user: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )   
    
    return {"email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "school_id": user.school_id,
            "user_id": user.user_id}


    

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
    
    return {"message": "Verification code deleted successfully"}


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
        existing_user.first_name = request.first_name
        existing_user.last_name = request.last_name
        existing_user.hashed_password = get_password_hash(request.password)
        existing_user.school_id = request.school_id
        db.commit()
        db.refresh(existing_user)
        return {"message": "User information updated successfully"}
    else: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="User not found.")
    

@router.post("/request-reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def request_reset_password(email: str, db: Session = Depends(get_db)):
    """_summary_: this router will be called by the student to request a password reset and email will be sent 
    to the school admin's email that the student is associated with. 

    Args:
        email (str): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    

@router.put("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    """_summary_ : 
    This router will only be called by the admin or super admin to reset the password for themselves 
    or for a student
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