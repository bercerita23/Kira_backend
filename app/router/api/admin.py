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
from app.model.points import Points

router = APIRouter()

@router.post("/student", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_student(student: StudentCreate,
                         db: Session = Depends(get_db),
                         admin: User = Depends(get_current_admin)): 
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
    
    # Create Points record for the new student
    new_points = Points(
        user_id=new_student.user_id,
        regular_points=0,
        premium_points=0
    )
    
    # Add both records and commit once
    db.add(new_student)
    db.add(new_points)
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
    students = db.query(User).join(Points).filter(User.school_id == admin.school_id, User.is_admin == False).all()
    res = {
        s.username: {
            "username": s.username,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "created_at": s.created_at,
            "last_login_time": s.last_login_time,
            "deactivated": s.deactivated,
            "points": s.points.points
        }
        for s in students
    }
    return { "student_data" : res}
    
@router.patch("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_student_password(request: PasswordResetWithUsername,
                                 db: Session = Depends(get_db), 
                                 admin: User = Depends(get_current_admin)):
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

@router.patch("/update", response_model=dict, status_code=status.HTTP_200_OK)
async def update_student_info(
    student_update: StudentUpdate, 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """_summary_: Update student information (first_name, last_name, email, notes)
    
    Args:
        username (str): Username of the student to update
        student_update (StudentUpdate): Updated student information
        db (Session): Database session
        admin (User): Current admin user
        
    Raises:
        HTTPException: If student not found or not in admin's school
        
    Returns:
        dict: Success message
    """
    # Find the student in admin's school
    student = db.query(User).filter(
        User.username == student_update.username,
        User.school_id == admin.school_id,
        User.is_admin == False
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Student not found in your school"
        )
    
    # Update only provided fields
    if student_update.first_name is not None:
        student.first_name = student_update.first_name
    if student_update.last_name is not None:
        student.last_name = student_update.last_name
    if student_update.email is not None:
        student.email = student_update.email
    if student_update.notes is not None:
        student.notes = student_update.notes
    if student_update.username is not None:
        student.username = student_update.username
    db.commit()
    return {"message": "Student information updated successfully"}

@router.patch("/deactivate_student", response_model=dict, status_code=status.HTTP_200_OK)
async def deactivate_student(
    request: StudentDeactivateRequest,
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """_summary_: Deactivate a student (set deactivated = True)
    
    Args:
        request (StudentDeactivateRequest): Contains username of student to deactivate
        db (Session): Database session
        admin (User): Current admin user
        
    Raises:
        HTTPException: If student not found or not in admin's school
        
    Returns:
        dict: Success message
    """
    # Find the student in admin's school
    student = db.query(User).filter(
        User.username == request.username,
        User.school_id == admin.school_id,
        User.is_admin == False
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Student not found in your school"
        )
    
    if student.deactivated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Student is already deactivated"
        )
    
    student.deactivated = True
    db.commit()
    return {"message": "Student deactivated successfully"}

@router.patch("/reactivate-student", response_model=dict, status_code=status.HTTP_200_OK)
async def reactivate_student(
    request: StudentReactivateRequest,
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """_summary_: Reactivate a deactivated student (set deactivated = False)
    
    Args:
        request (StudentReactivateRequest): Contains username of student to reactivate
        db (Session): Database session
        admin (User): Current admin user
        
    Raises:
        HTTPException: If student not found or not in admin's school
        
    Returns:
        dict: Success message
    """
    # Find the student in admin's school
    student = db.query(User).filter(
        User.username == request.username,
        User.school_id == admin.school_id,
        User.is_admin == False
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Student not found in your school"
        )
    
    if not student.deactivated:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Student is already active"
        )
    
    student.deactivated = False
    db.commit()
    return {"message": "Student reactivated successfully"}