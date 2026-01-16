from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schema.auth_schema import *
from app.model.users import User
from app.router.dependencies import *
from app.router.api.logics.auth_logic import (
    login_student_logic,
    login_administrator_logic,
    register_admin_logic,
    cleanup_expired_codes,
    request_reset_password_logic,
    reset_admin_password_logic,
    get_all_schools_logic,
    resend_verification_code_logic
)


router = APIRouter()

@router.post("/login-stu", response_model=Token, status_code=status.HTTP_200_OK)
async def login_student(request: LoginRequestStudent, 
                        db: Session = Depends(get_db)):
    """Student login endpoint that handles both username and email authentication.

    Args:
        request (LoginRequestStudent): Login request with username/email and password
        db (Session): Database session

    Raises:
        HTTPException: When user not found or credentials are incorrect

    Returns:
        Token: Access token for successful authentication
    """
    return login_student_logic(db, request)
        

@router.post("/login-ada", response_model=Token, status_code=status.HTTP_200_OK)
async def login_administrator(request: LoginRequestAdmin, 
                              db: Session = Depends(get_db)):
    """Administrator login endpoint for admin and super admin users.

    Args:
        request (LoginRequestAdmin): Login request with email and password
        db (Session): Database session

    Raises:
        HTTPException: When user not found, is not an admin, is deactivated, or credentials are incorrect

    Returns:
        Token: Access token for successful authentication
    """
    return login_administrator_logic(db, request)

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
    return register_admin_logic(db, request)


@router.post("/request-reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def request_reset_password(request_body: ResetPasswordRequest, 
                                 db: Session = Depends(get_db)):
    """Handle password reset request for both admins and students.
    
    For admins: Sends reset password email with verification code.
    For students: Sends reset password request to admins in the school.
    
    Args:
        request_body (ResetPasswordRequest): Contains email or username
        db (Session): Database session

    Returns:
        dict: Success message
    """
    return request_reset_password_logic(db, request_body)
        
@router.post("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_admin_password(request: PasswordResetWithEmail, db: Session = Depends(get_db)): 
    """Reset admin password with unexpired verification code.
    
    Process:
    1. Check the code is valid and not expired
    2. Update password 
    3. Delete code

    Args:
        request (PasswordResetWithEmail): Contains email, code, and new password
        db (Session): Database session

    Raises:
        HTTPException: Code expired, incorrect code, or user not found

    Returns:
        dict: Success message
    """
    return reset_admin_password_logic(db, request)


@router.get("/school", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_school(db: Session = Depends(get_db)):
    """Get all active schools.
    
    Args:
        db (Session): Database session
        
    Returns:
        dict: Dictionary containing list of active schools
    """
    return get_all_schools_logic(db)

@router.post("/resend-verification", response_model=dict, status_code=status.HTTP_200_OK)
async def resend_verification_code(request: ResendVerificationEmail, 
                                   db: Session = Depends(get_db)):
    """Resend verification code for admin registration or password reset.
    
    Automatically detects the purpose:
    - If email exists in TempAdmin (unverified) → Resends registration verification
    - If email exists in User as admin → Resends password reset verification
    
    Args:
        request (ResendVerificationEmail): Contains only email
        db (Session): Database session
        
    Returns:
        dict: Success message
    """
    return resend_verification_code_logic(db, request)