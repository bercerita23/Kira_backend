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


router = APIRouter()

@router.post("/login-stu", response_model=Token, status_code=status.HTTP_200_OK)
async def login_student(request: LoginRequestStudent, 
                        db: Session = Depends(get_db)):

    """Student login endpoint that handles both username and email authentication


    Args:
        request (LoginRequestStudent): Login request with username/email and password
        db (Session): Database session

    Raises:
        HTTPException: When user not found or credentials are incorrect

    Returns:
        Token: Access token for successful authentication
    """
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
    # Determine user role
    role = "admin" if (user.is_admin) else "student"


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
        role=role,
        school_id=school_id,
        expires_delta=access_token_expires
    )
    
    # Update last login time
    user.last_login_time = datetime.now()
    db.commit()
    
    return {"access_token": access_token, "token_type": "bearer"}
        

@router.post("/login-ada", response_model=Token, status_code=status.HTTP_200_OK)
async def login_administrator(request: LoginRequestAdmin, 
                              db: Session = Depends(get_db)):

    """Administrator login endpoint for admin and super admin users


    Args:
        request (LoginRequestAdmin): Login request with email and password
        db (Session): Database session

    Raises:
        HTTPException: When user not found, is not an admin, is deactivated, or credentials are incorrect

    Returns:
        Token: Access token for successful authentication
    """

    user = db.query(User).filter(User.email  == request.email).first()

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
    
    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Credentials"
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

@router.post("/register-admin", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(request: AdminCreate, 
                   db: Session = Depends(get_db)):

    """Register a new admin user with verification code validation
    
    Process:

    1. Check the verification code: valid & not expired 
    2. Check the information user entered is correct 
    3. Add user into the table 
    4. Delete the verification code
    5. Change the "verified" on temp_admins to true
    
    Args:
        request (AdminCreate): Admin creation request with email, school_id, firstname, lastname, code, password
        db (Session): Database session

    Raises:
        HTTPException: When verification code is invalid/expired, invitation not found, or information mismatch

    Returns:
        dict: Success message
    """
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == request.email,
        VerificationCode.code == request.code,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code: 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either the verification code has expired, or an incorrect one was inputted. Please check again")
    
    temp_admin = db.query(TempAdmin).filter(TempAdmin.email == request.email).first()
    if not temp_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if (request.school_id != temp_admin.school_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect school was chosen")
    if  (request.first_name != temp_admin.first_name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect First Name was inputted")
    if (request.last_name != temp_admin.last_name): 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect Last Name was inputted")


    admin = User(
        user_id = temp_admin.user_id, 
        school_id = temp_admin.school_id, 
        email = temp_admin.email, 
        hashed_password = get_password_hash(request.password), 
        first_name = temp_admin.first_name, 
        last_name = temp_admin.last_name, 
        created_at = datetime.now(), 
        is_super_admin = False, 
        is_admin = True, 
        username = None, 
        deactivated = False
    )

    temp_admin.verified = True

    db.add(admin)
    db.delete(verification_code)
    db.commit()
    return {"message": "You have been registered successfully."}

def cleanup_expired_codes(db: Session, email: str):
    """Remove expired verification codes for a specific email"""
    db.query(VerificationCode).filter(
        VerificationCode.email == email,
        VerificationCode.expires_at <= datetime.now()
    ).delete(synchronize_session=False)
    db.commit()

@router.post("/request-reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def request_reset_password(request_body: ResetPasswordRequest, 
                                 db: Session = Depends(get_db)):
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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    # Add this validation
        if not user.is_admin and not user.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Email-based password reset is only available for administrators"
            )        
        code = str(uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=180)
        
        # Check if there's an existing verification code for this email
        existing_code = db.query(VerificationCode).filter(
            VerificationCode.email == user.email
        ).first()
        
        if existing_code:
            # Update existing code instead of creating new one
            existing_code.code = code
            existing_code.expires_at = expires_at
        else:
            # Create new code only if none exists
            reset_code_entry = VerificationCode(
                email=user.email,
                code=code,
                expires_at=expires_at
            )
            db.add(reset_code_entry)
        
        db.commit()
        
        # send the reset password email to the admin
        send_admin_verification_email(user.email, "forgot-password/reset", code, user.first_name)
        
        return {"message": f"Reset password email sent to {user.email}"}
    
    else: # Student is trying to reset password
        student = db.query(User).filter(User.username == request_body.username).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")   
        
        res = db.query(User).filter(User.school_id == student.school_id, User.is_admin == True).all()
        # send the reset password request to the admin's email
        admin_emails = [r.email for r in res]
        for email in admin_emails: 
            print(email)
            send_reset_request_to_admin("login", email,
                                    student.username, student.school_id, student.first_name)
        
        return {"message": f"Reset password email sent"}
        
@router.post("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_admin_password(request: PasswordResetWithEmail, db: Session = Depends(get_db)): 
    """_summary_ let an admin resets password with unexpired code
    1. check the code
    2. udpate password 
    3. delete code

    Args:
        request (PasswordResetWithEmail): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_: Code expired or incorrect code
        HTTPException: _description_: User not found

    Returns:
        _type_: _description_
    """
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == request.email,
        VerificationCode.code == request.code,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code: 
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code expired or incorrect code.")
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password 
    db.delete(verification_code)
    db.commit()

    return {"message": "Password reset successfully"}


@router.get("/school", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_school(db: Session = Depends(get_db)):
    temp = db.query(School).filter(School.status == SchoolStatus.active).all()
    res = [{
        "school_id": school.school_id,
        "name": school.name,
        "status": school.status.value,
    } for school in temp]
    return {"schools": res}