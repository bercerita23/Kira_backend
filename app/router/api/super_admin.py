from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from datetime import datetime
from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.temp_admins import TempAdmin
from app.schema.super_admin_schema import *
from typing import Any, Dict
from app.router.aws_ses import *
from app.router.auth_util import *
from uuid import uuid4
from app.model.schools import School
from app.router.dependencies import *
from datetime import datetime

router = APIRouter()

@router.post("/invite", response_model=dict, status_code=status.HTTP_200_OK)
async def invite(
    request: Invitation, db: Session = Depends(get_db), super_admin: User = Depends(get_current_super_admin)
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
    return {"message": f"Invitation has been sent to {request.email}"}

@router.post("/deactivate_admin", response_model=dict)
async def deactivate_admin(request: AdminActivation, 
                           db: Session = Depends(get_db), 
                           super_admin: User = Depends(get_current_super_admin)):
    """deactivate an admin

    Args:
        request (AdminActivation): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).
        super_admin (User, optional): _description_. Defaults to Depends(get_current_super_admin).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    admin = db.query(User).filter(User.email == request.email).first()
    if not admin: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with {request.email} not found.",
        )
    admin.deactivated = True 
    db.commit()
    db.refresh(admin)
    time = datetime.now()
    return {
        "message": "Admin deactivated successfully", 
        "admin_email": f"{request.email}", 
        "deactivated_at": f"{time}"
    }

@router.post("/reactivate_admin")
async def reactivate_admin(request: AdminActivation, 
                           db: Session = Depends(get_db), 
                           super_admin: User = Depends(get_current_super_admin)): 
    """reactivate an admin

    Args:
        request (AdminActivation): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).
        super_admin (User, optional): _description_. Defaults to Depends(get_current_super_admin).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    admin = db.query(User).filter(User.email == request.email).first()
    if not admin: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Admin with {request.email} not found.",
        )
    admin.deactivated = False 
    time = datetime.now()
    db.commit()
    db.refresh(admin)
    return {
        "message": "Admin activated successfully", 
        "admin_email": f"{request.email}", 
        "deactivated_at": f"{time}"
    }

@router.get("/")
def get_all_users(db: Session = Depends(get_db), 
                  super_admin: User = Depends(get_current_super_admin)):
    users = db.query(User).all()
    return { "Hello_Form:" : users }

@router.get("/schools_with_admins", response_model=SchoolsResponse, status_code=status.HTTP_200_OK)
async def get_schools_with_admins(
    db: Session = Depends(get_db), 
    super_admin: User = Depends(get_current_super_admin)
):
    """enchanced fetch schools with admins

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        super_admin (User, optional): _description_. Defaults to Depends(get_current_super_admin).

    Returns:
        _type_: _description_
    """
    schools = db.query(School).all()
    result = []

    for school in schools:
        admins = db.query(User).filter(
            User.school_id == school.school_id,
            User.is_admin == True
        ).all()

        students_count = db.query(User).filter(
            User.school_id == school.school_id,
            User.is_admin == False
        ).count()

        school_data = SchoolWithAdminsOut(
            school_id=school.school_id,
            name=school.name,
            email=school.email,
            data_fetched_at=datetime.now(),
            admins=[AdminOut.model_validate(admin) for admin in admins],
            student_count=students_count
        )

        result.append(school_data)

    return {"schools": result}