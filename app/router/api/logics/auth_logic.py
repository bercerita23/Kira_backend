from datetime import timedelta, datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from uuid import uuid4
from typing import Dict, Any

from app.router.auth_util import verify_password, create_access_token, get_password_hash
from app.config import settings
from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.temp_admins import TempAdmin
from app.model.schools import School, SchoolStatus
from app.router.aws_ses import send_admin_verification_email, send_reset_request_to_admin
from app.schema.auth_schema import (
    LoginRequestStudent,
    LoginRequestAdmin,
    AdminCreate,
    ResetPasswordRequest,
    PasswordResetWithEmail,
    ResendVerificationEmail
)


def login_student_logic(
    db: Session,
    request: LoginRequestStudent
) -> Dict[str, str]:
    """Student login logic that handles both username and email authentication.

    Args:
        db (Session): Database session
        request (LoginRequestStudent): Login request with username/email and password

    Raises:
        HTTPException: When user not found or credentials are incorrect

    Returns:
        Dict[str, str]: Access token and token type
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


def login_administrator_logic(
    db: Session,
    request: LoginRequestAdmin
) -> Dict[str, str]:
    """Administrator login logic for admin and super admin users.

    Args:
        db (Session): Database session
        request (LoginRequestAdmin): Login request with email and password

    Raises:
        HTTPException: When user not found, is not an admin, is deactivated, or credentials are incorrect

    Returns:
        Dict[str, str]: Access token and token type
    """
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
        # Ensure both are strings and strip whitespace
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
    role = None
    school_id = None
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


def register_admin_logic(
    db: Session,
    request: AdminCreate
) -> Dict[str, str]:
    """Register a new admin user with verification code validation.
    
    Process:
    1. Check the verification code: valid & not expired 
    2. Check the information user entered is correct 
    3. Add user into the table 
    4. Delete the verification code
    5. Change the "verified" on temp_admins to true
    
    Args:
        db (Session): Database session
        request (AdminCreate): Admin creation request with email, school_id, firstname, lastname, code, password

    Raises:
        HTTPException: When verification code is invalid/expired, invitation not found, or information mismatch

    Returns:
        Dict[str, str]: Success message
    """
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == request.email,
        VerificationCode.code == request.code,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either the verification code has expired, or an incorrect one was inputted. Please check again"
        )
    
    temp_admin = db.query(TempAdmin).filter(TempAdmin.email == request.email).first()
    if not temp_admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found."
        )

    if (request.school_id != temp_admin.school_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect school was chosen"
        )
    if (request.first_name != temp_admin.first_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect First Name was inputted"
        )
    if (request.last_name != temp_admin.last_name): 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect Last Name was inputted"
        )

    admin = User(
        user_id=temp_admin.user_id, 
        school_id=temp_admin.school_id, 
        email=temp_admin.email, 
        hashed_password=get_password_hash(request.password), 
        first_name=temp_admin.first_name, 
        last_name=temp_admin.last_name, 
        created_at=datetime.now(), 
        is_super_admin=False, 
        is_admin=True, 
        username=None, 
        deactivated=False
    )

    temp_admin.verified = True

    db.add(admin)
    db.delete(verification_code)
    db.commit()
    return {"message": "You have been registered successfully."}


def cleanup_expired_codes(db: Session, email: str) -> None:
    """Remove expired verification codes for a specific email.
    
    Args:
        db (Session): Database session
        email (str): Email address to clean up codes for
    """
    db.query(VerificationCode).filter(
        VerificationCode.email == email,
        VerificationCode.expires_at <= datetime.now()
    ).delete(synchronize_session=False)
    db.commit()


def request_reset_password_logic(
    db: Session,
    request_body: ResetPasswordRequest
) -> Dict[str, str]:
    """Handle password reset request for both admins and students.
    
    For admins: Sends reset password email with verification code.
    For students: Sends reset password request to admins in the school.
    
    Args:
        db (Session): Database session
        request_body (ResetPasswordRequest): Contains email or username

    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: When user not found or invalid request
    """
    if request_body.email:  # Admin is trying to reset password
        user = db.query(User).filter(User.email == request_body.email).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
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
    
    else:  # Student is trying to reset password
        student = db.query(User).filter(User.username == request_body.username).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        res = db.query(User).filter(
            User.school_id == student.school_id,
            User.is_admin == True
        ).all()
        
        # send the reset password request to the admin's email
        admin_emails = [r.email for r in res]
        for email in admin_emails: 
            send_reset_request_to_admin(
                "login",
                email,
                student.username,
                student.school_id,
                student.first_name
            )
        
        return {"message": f"Reset password email sent"}


def reset_admin_password_logic(
    db: Session,
    request: PasswordResetWithEmail
) -> Dict[str, str]:
    """Reset admin password with unexpired verification code.
    
    Process:
    1. Check the code is valid and not expired
    2. Update password 
    3. Delete code

    Args:
        db (Session): Database session
        request (PasswordResetWithEmail): Contains email, code, and new password

    Raises:
        HTTPException: Code expired, incorrect code, or user not found

    Returns:
        Dict[str, str]: Success message
    """
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == request.email,
        VerificationCode.code == request.code,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code: 
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code expired or incorrect code."
        )
    
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password 
    db.delete(verification_code)
    db.commit()

    return {"message": "Password reset successfully"}


def get_all_schools_logic(db: Session) -> Dict[str, Any]:
    """Get all active schools.
    
    Args:
        db (Session): Database session
        
    Returns:
        Dict[str, Any]: Dictionary containing list of active schools
    """
    temp = db.query(School).filter(School.status == SchoolStatus.active).all()
    res = [{
        "school_id": school.school_id,
        "name": school.name,
        "status": school.status.value,
    } for school in temp]
    return {"schools": res}


def resend_verification_code_logic(
    db: Session,
    request: ResendVerificationEmail
) -> Dict[str, str]:
    """Resend verification code for admin registration or password reset.
    
    Automatically detects the purpose:
    - If email exists in TempAdmin (unverified) → Resends registration verification
    - If email exists in User as admin → Resends password reset verification
    
    Args:
        db (Session): Database session
        request (ResendVerificationEmail): Contains only email
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If email not found in either scenario
    """
    # First check: Is this for registration? (unverified temp admin)
    temp_admin = db.query(TempAdmin).filter(
        TempAdmin.email == request.email,
        TempAdmin.verified == False
    ).first()
    
    if temp_admin:
        # Generate new code for registration
        code = str(uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=180)
        
        existing_code = db.query(VerificationCode).filter(
            VerificationCode.email == request.email
        ).first()
        
        if existing_code:
            existing_code.code = code
            existing_code.expires_at = expires_at
        else:
            verification_code = VerificationCode(
                email=request.email,
                code=code,
                expires_at=expires_at
            )
            db.add(verification_code)
        
        db.commit()
        send_admin_verification_email(request.email, "register-admin", code, temp_admin.first_name)
        return {"message": f"Registration verification code resent to {request.email}"}
    
    # Second check: Is this for password reset? (existing admin user)
    user = db.query(User).filter(User.email == request.email).first()
    
    if user and (user.is_admin or user.is_super_admin):
        # Generate new code for password reset
        code = str(uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=180)
        
        existing_code = db.query(VerificationCode).filter(
            VerificationCode.email == request.email
        ).first()
        
        if existing_code:
            existing_code.code = code
            existing_code.expires_at = expires_at
        else:
            verification_code = VerificationCode(
                email=request.email,
                code=code,
                expires_at=expires_at
            )
            db.add(verification_code)
        
        db.commit()
        send_admin_verification_email(request.email, "forgot-password/reset", code, user.first_name)
        return {"message": f"Password reset verification code resent to {request.email}"}
    
    # Email not found in either scenario
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No pending registration or password reset found for this email"
    )
