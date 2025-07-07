from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schema.admin_schema import *
from app.router.auth_util import *
from app.model.users import User
from app.router.dependencies import *
from typing import List
from datetime import datetime

router = APIRouter()

@router.post("/student", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_student(student: StudentCreate, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)): 
    """_summary_ admin will call this route to create a student with 
    1. username
    2. a password
    3. first name 
    4. last ame 
    5. and a username

    Args:
        student (StudentCreate): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).
        admin (User, optional): _description_. Defaults to Depends(get_current_admin).

    Returns:
        _type_: _description_
    """
    new_student = User(
        user_id=generate_unique_user_id(db), 
        username=student.username,
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
    print("admin is: ", admin)
    students = db.query(User).filter(User.school_id == admin.school_id, User.is_admin == False).all()
    res = {
        s.username: {
            "username": s.username,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "created_at": s.created_at,
            "last_login_time": s.last_login_time,
            "deactivated": s.deactivated,
        }
        for s in students
    }
    return { "student_data" : res}
    
@router.patch("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_student_password(request: PasswordResetWithUsername, db: Session = Depends(get_db)):
    """_summary_ : 
    
    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_ a message in JSON format indicating success with 200
    """
        
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password 
    db.commit()

    return {"message": "Password reset successfully"}