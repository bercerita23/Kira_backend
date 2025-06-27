from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from datetime import datetime
from app.schema.admin_schema import *
from app.router.auth_util import *
from app.model.users import User
from app.router.dependencies import *
from uuid import uuid4
router = APIRouter()

@router.post("/student", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_student(student: StudentCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)): 

    new_student = User(
        user_id=generate_unique_user_id(db), 
        email=student.email,
        hashed_password=get_password_hash(student.password),
        first_name=student.first_name,
        last_name=student.last_name,
        school_id=admin.school_id
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)
    return {"message": "Student created successfully", "user_id": new_student.user_id}

@router.get("/students", response_model=dict, status_code=status.HTTP_200_OK)
async def get_students(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)): 
    """_summary_: 
    This router will only be called by the admin or super admin to get all students in their school
    Returns:
        _type_: _description_ a list of students in JSON format with 200
    """
    students = db.query(User).filter(User.school_id == admin.school_id).all()
    return {"students": students}


# TODO: separate the routes 
@router.patch("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_student_password(request: PasswordReset, db: Session = Depends(get_db)):
    """_summary_ : 
    This router will only be called by the admin or super admin to reset the password for themselves 
    or for a student. 
    1. if the request contains an email, it means the admin is trying to reset their own password

    2. if the request contains a user_id, it means the admin is trying to reset the password for a student
    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_ a message in JSON format indicating success with 200
    """
    user = None
    if request.email: # Admin is trying to reset their own password
        user = db.query(User).filter(User.email == request.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
    else: # Admin is trying to reset password for a student
        user = db.query(User).filter(User.user_id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password 
    db.commit()

    return {"message": "Password reset successfully"}