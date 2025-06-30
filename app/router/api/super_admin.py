from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from datetime import datetime
from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.temp_admins import TempAdmin
from app.schema.super_admin_schema import Invitation
from typing import Any, Dict
from app.router.aws_ses import *
from app.router.auth_util import *
from uuid import uuid4

router = APIRouter()

@router.post("/invite", response_model=dict, status_code=status.HTTP_200_OK)
async def invite(
    request: Invitation, db: Session = Depends(get_db) #TODO: add a dependency to get super admin user)
) -> Dict[str, Any]:
    """_summary_: Super admin will call this endpoint to sned an invitation email to a new school admin to register. 
    1. If the email exists in the DB, raise an exception. 
    2. Generate a verification code and store it in the database
    3. Temporarily store the user information in the temp_admins table to compare later
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
    temp_admin = TempAdmin(
        user_id = generate_unique_user_id(db), 
        school_id = request.school_id, 
        email = request.email, 
        first_name = request.first_name, 
        last_name = request.last_name, 
        verified = False, 
        created_at = datetime.now() 
    )
    db.add(temp_admin)
    db.commit()
    db.refresh(temp_admin)
    
    send_admin_invite_email(temp_admin.email, "signup", code, 
                            temp_admin.user_id,
                            temp_admin.school_id,
                            temp_admin.first_name, 
                            temp_admin.last_name)
    return {"message": f"Verification code was sent to {request.email}"}