from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from datetime import datetime, timedelta
from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.temp_admins import TempAdmin
from app.schema.super_admin_schema import *
from typing import Any, Dict
from app.router.aws_ses import *
from app.router.auth_util import *
from uuid import uuid4
from app.model.schools import School
from app.model.topics import Topic
from app.router.dependencies import *
from datetime import datetime
from app.schema.super_admin_schema import NewSchool, UpdateSchool
from app.model.schools import SchoolStatus
import random

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
    # 2. Remove any existing temp_admin with this email
    db.query(TempAdmin).filter(TempAdmin.email == request.email).delete()
    db.commit()
    # 3. Remove any existing verification code for this email
    db.query(VerificationCode).filter(VerificationCode.email == request.email).delete()
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
    users = db.query(User).filter(User.deactivated.is_(False)).all()
    
    # Enrich users with school name
    enriched_users = []
    for user in users:
        user_dict = {
            "user_id": user.user_id,
            "school_id": user.school_id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "created_at": user.created_at,
            "notes": user.notes,
            "last_login_time": user.last_login_time,
            "is_super_admin": user.is_super_admin,
            "is_admin": user.is_admin,
            "username": user.username,
            "deactivated": user.deactivated,
            "grade": user.grade,
            "school_name": user.school.name if user.school else None
        }
        enriched_users.append(user_dict)
    
    return {"Hello_Form:": enriched_users}

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
    schools = db.query(School).filter_by(School.status == SchoolStatus.active).all()
    result = []

    for school in schools:
        admins = db.query(User).filter(
            User.school_id == school.school_id,
            User.is_admin == True,
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

@router.post('/addschool', status_code=status.HTTP_201_CREATED)
async def create_new_school(
    new_school: NewSchool,
    db: Session = Depends(get_db),
    user = Depends(get_current_super_admin)
):
    if not new_school.email:
        raise HTTPException(400, detail="Email was not provided")
    if not new_school.name:
        raise HTTPException(400, detail="name was not provided")
    if not new_school.telephone:
        raise HTTPException(400, detail="Phone number was not provided")
    if not new_school.address:
        raise HTTPException(400, detail="Address was not provided")

    # Validate prompts: either all three are provided or none
    prompts = [new_school.question_prompt, new_school.image_prompt, new_school.kira_chat_prompt]
    filled_prompts = [p for p in prompts if p is not None and p.strip()]
    
    if 0 < len(filled_prompts) < 3:
        raise HTTPException(
            status_code=400,
            detail="All three prompts (question_prompt, image_prompt, kira_chat_prompt) must be provided together or all left empty"
        )

    exists_by_name = db.query(School).filter_by(name=new_school.name).first()
    if exists_by_name:
        raise HTTPException(422, detail="School with that name already exists")

    # generate unique 8-digit school_id
    while True:
        candidate = str(random.randint(10**7, 10**8 - 1))
        exists_by_id = db.query(School).filter_by(school_id=candidate).first() 
        if not exists_by_id:
            break

    school = School(
        email=new_school.email,
        name=new_school.name,
        address=new_school.address,
        telephone=new_school.telephone,
        school_id=candidate,
        status=SchoolStatus.active,
        max_questions=new_school.max_questions if new_school.max_questions is not None else 5,
        question_prompt=new_school.question_prompt,
        image_prompt=new_school.image_prompt,
        kira_chat_prompt=new_school.kira_chat_prompt
    )

    db.add(school)
    db.commit()
    db.refresh(school)

    return {
        "message": "school created",
        "school": {
            "school_id": school.school_id,
            "name": school.name,
            "email": school.email,
            "telephone": school.telephone,
            "address": school.address,
            "status": school.status.value,
            "max_questions": school.max_questions
        },
    }

@router.post('/removeschool/{school_id}', status_code=status.HTTP_202_ACCEPTED)
async def delete_school(school_id: str, db:Session = Depends(get_db), user: User = Depends(get_current_super_admin)):
    school = db.get(School, school_id)
    if not school or school.status != SchoolStatus.active :
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            details="School with that id is not found."
            )
    school.status = SchoolStatus.inactive
    db.commit()
    return {
        "message": "school status updated"
    }

@router.get('/inactiveschools')
async def get_inactive_schools(db: Session = Depends(get_db), user: User = Depends(get_current_super_admin)):
    schools = db.query(School).filter(
        (School.status == SchoolStatus.inactive) | (School.status == SchoolStatus.suspended)
    ).all()
    if not schools:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="there is no schools that are inactive or suspended"
        )
    return {
        "schools": schools
    }

@router.post("/activateschool/{school_id}", status_code=status.HTTP_202_ACCEPTED)
async def activate_school(school_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_super_admin)):
    school = db.get(School, school_id)
    if not school or school.status not in [SchoolStatus.inactive, SchoolStatus.suspended]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="School with that id is not found"
    )
    if(school.status == SchoolStatus.inactive or school.status == SchoolStatus.suspended):
        school.status = SchoolStatus.active
    db.commit()
    return {
        "message": "school status updated", 
    }

@router.post("/deleteschool/{school_id}")
def suspend_school(
    school_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
):
    school = db.get(School, school_id)
    if not school:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="School not found")

    if school.status == SchoolStatus.suspended:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="School already suspended")

    school.status = SchoolStatus.suspended
    db.commit()
    db.refresh(school)

    return {"message": "School status updated", "school_id": school.school_id, "status": school.status.value}

@router.post('/updateschool', status_code=status.HTTP_200_OK)
def update_school(
    updated_school: UpdateSchool,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin)):

    school = db.get(School,  updated_school.school_id)
    
    if not school: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="School with that id was not found"
            )
    if school.email is not updated_school.email: 
        school.email = updated_school.email
    if school.address is not updated_school.address: 
        school.address = updated_school.address
    if school.telephone is not updated_school.telephone: 
        school.telephone = updated_school.telephone 
    if school.name is not updated_school.name: 
        school.name = updated_school.name 
    db.commit()
    return {
        "message": "School is updated"
    }

@router.get("/schools", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_school(db: Session = Depends(get_db)):
    temp = db.query(School).filter(School.status == SchoolStatus.active).all()
    res = [{
        "school_id": school.school_id,
        "name": school.name,
        "status": school.status.value,
        "email" : school.email, 
        "telephone" : school.telephone, 
        "address" : school.address
    } for school in temp]
    return {"schools": res}
