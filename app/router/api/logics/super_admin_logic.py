from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime, timedelta
from typing import Dict, Any, List
from uuid import uuid4
import random

from app.model.users import User
from app.model.verification_codes import VerificationCode
from app.model.temp_admins import TempAdmin
from app.model.schools import School, SchoolStatus
from app.schema.super_admin_schema import (
    Invitation, AdminActivation, AdminOut, SchoolWithAdminsOut, 
    SchoolsResponse, NewSchool, UpdateSchool
)
from app.router.aws_ses import send_admin_invite_email
from app.router.auth_util import generate_unique_user_id


def invite_admin_logic(db: Session, request: Invitation) -> Dict[str, Any]:
    """Super admin will call this function to send an invitation email to a new school admin to register.
    
    1. If the email exists in the DB, raise an exception. 
    2. Generate a verification code and store it in the database
    3. Temporarily store the user information in the temp_admins table to compare later
    4. Send the code to the email address provided in the request with SES.
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


def deactivate_admin_logic(db: Session, request: AdminActivation) -> Dict[str, Any]:
    """Deactivate an admin."""
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


def reactivate_admin_logic(db: Session, request: AdminActivation) -> Dict[str, Any]:
    """Reactivate an admin."""
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


def get_all_users_logic(db: Session) -> Dict[str, Any]:
    """Get all active users."""
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


def get_schools_with_admins_logic(db: Session) -> SchoolsResponse:
    """Enhanced fetch schools with admins."""
    schools = db.query(School).filter(School.status == SchoolStatus.active).all()
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

    return SchoolsResponse(schools=result)


def create_new_school_logic(db: Session, new_school: NewSchool) -> Dict[str, Any]:
    """Create a new school."""
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


def delete_school_logic(db: Session, school_id: str) -> Dict[str, str]:
    """Delete (deactivate) a school."""
    school = db.get(School, school_id)
    if not school or school.status != SchoolStatus.active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="School with that id is not found."
        )
    school.status = SchoolStatus.inactive
    db.commit()
    return {
        "message": "school status updated"
    }


def get_inactive_schools_logic(db: Session) -> Dict[str, List[School]]:
    """Get all inactive or suspended schools."""
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


def activate_school_logic(db: Session, school_id: str) -> Dict[str, str]:
    """Activate a school."""
    school = db.get(School, school_id)
    if not school or school.status not in [SchoolStatus.inactive, SchoolStatus.suspended]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="School with that id is not found"
        )
    if school.status == SchoolStatus.inactive or school.status == SchoolStatus.suspended:
        school.status = SchoolStatus.active
    db.commit()
    return {
        "message": "school status updated", 
    }


def suspend_school_logic(db: Session, school_id: str) -> Dict[str, Any]:
    """Suspend a school."""
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


def update_school_logic(db: Session, updated_school: UpdateSchool) -> Dict[str, Any]:
    """Update a school."""
    school = db.get(School, updated_school.school_id)
    
    if not school: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="School with that id was not found"
        )
    
    # Check if any prompts are being updated
    prompts_to_update = [
        updated_school.question_prompt,
        updated_school.image_prompt,
        updated_school.kira_chat_prompt
    ]
    
    provided_prompts = [p for p in prompts_to_update if p is not None]
    
    # Check if all current prompts are NULL
    current_prompts_are_null = all([
        school.question_prompt is None,
        school.image_prompt is None,
        school.kira_chat_prompt is None
    ])
    
    # RULE 1: If current prompts are ALL NULL, user MUST provide all 3 or none
    if current_prompts_are_null and 0 < len(provided_prompts) < 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="When prompts are empty, all three prompts (question_prompt, image_prompt, kira_chat_prompt) must be provided together"
        )
    
    # RULE 2: If trying to remove/empty prompts, all 3 must be provided and all must be empty
    if len(provided_prompts) > 0:
        # Check which provided prompts are empty strings
        empty_prompts = [p for p in provided_prompts if not p or not p.strip()]
        
        # If any prompt is being emptied
        if len(empty_prompts) > 0:
            # Must provide all 3 prompts when trying to empty
            if len(provided_prompts) < 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="To remove custom prompts, all three prompts must be provided together"
                )
            # All 3 must be empty (no partial emptying)
            if len(empty_prompts) != 3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="All three prompts must be emptied together. Cannot remove only some prompts."
                )
    
    # Update basic fields
    if school.email != updated_school.email: 
        school.email = updated_school.email
    if school.address != updated_school.address: 
        school.address = updated_school.address
    if school.telephone != updated_school.telephone: 
        school.telephone = updated_school.telephone 
    if school.name != updated_school.name: 
        school.name = updated_school.name
    
    # Update max_questions if provided
    if updated_school.max_questions is not None:
        school.max_questions = updated_school.max_questions
    
    # Update prompts - convert empty strings to None
    if updated_school.question_prompt is not None:
        school.question_prompt = updated_school.question_prompt.strip() if updated_school.question_prompt.strip() else None
    if updated_school.image_prompt is not None:
        school.image_prompt = updated_school.image_prompt.strip() if updated_school.image_prompt.strip() else None
    if updated_school.kira_chat_prompt is not None:
        school.kira_chat_prompt = updated_school.kira_chat_prompt.strip() if updated_school.kira_chat_prompt.strip() else None
    
    db.commit()
    db.refresh(school)
    
    return {
        "message": "School is updated",
        "school": {
            "school_id": school.school_id,
            "name": school.name,
            "custom_prompts_active": school.question_prompt is not None
        }
    }


def get_all_schools_logic(db: Session) -> Dict[str, List[Dict[str, Any]]]:
    """Get all active schools."""
    temp = db.query(School).filter(School.status == SchoolStatus.active).all()
    res = [{
        "school_id": school.school_id,
        "name": school.name,
        "status": school.status.value,
        "email": school.email, 
        "telephone": school.telephone, 
        "address": school.address,
        "max_questions": school.max_questions,
        "question_prompt": school.question_prompt,
        "image_prompt": school.image_prompt,
        "kira_chat_prompt": school.kira_chat_prompt
    } for school in temp]
    return {"schools": res}


def get_default_prompts_logic() -> Dict[str, Any]:
    """Return default prompts for question generation, image generation, and Kira chat.
    Used when creating new schools or when schools don't have custom prompts.
    """
    try:
        # Read question generation prompt
        with open("app/gen_ai_prompts/open_ai_role_prompt.txt", encoding="utf-8") as f:
            default_question_prompt = f.read()
        
        # Read image generation prompt
        with open("app/gen_ai_prompts/gemini_role_prompt.txt", encoding="utf-8") as f:
            default_image_prompt = f.read()
        
        # Default Kira chat prompt (same as used in users.py)
        default_kira_chat_prompt = "You are Kira, an english tutor for indonesian students. you can also be refered to as Kira Monkey and you also respond if they are trying to greet you or asking hows is your day."
        
        return {
            "default_max_questions": 5,
            "default_question_prompt": default_question_prompt,
            "default_image_prompt": default_image_prompt,
            "default_kira_chat_prompt": default_kira_chat_prompt
        }
        
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prompt file not found: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading default prompts: {str(e)}"
        )
