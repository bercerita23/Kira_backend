from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.schema.admin_schema import *
from app.router.auth_util import *
from app.model.topics import Topic 
from app.model.users import User
from app.router.dependencies import *
from typing import List, Annotated
from datetime import datetime
from app.model.points import Points
import hashlib
import boto3
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError
from app.router.aws_s3 import *
from app.router.aws_ses import *
import fitz 

router = APIRouter()
s3_service = S3Service()

@router.get("/student/{username}", response_model=dict, status_code=status.HTTP_200_OK)
async def get_detail_student_info(
    username: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    # 1. Fetch user and check school
    user = db.query(User).filter(
        User.username == username,
        User.school_id == admin.school_id,
        User.is_admin == False
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Student not found in your school")

    # 2. Points
    points = user.points.points if user.points else 0

    # 3. Streak
    streak = user.streak.current_streak if user.streak else 0

    # 4. Badges
    badges = [
        {
            "badge_id": b.badge_id,
            "name": b.badge.name,
            "earned_at": b.earned_at,
            "description": b.badge.description,
            "icon_url": b.badge.icon_url,
        }
        for b in user.badges
    ]
    badges_earned = len(badges)

    # 5. Quiz Attempts
    attempts = user.attempts
    quiz_history = {}
    for a in attempts:
        if a.quiz_id not in quiz_history:
            quiz_history[a.quiz_id] = {
                "quiz_name": a.quiz.name if a.quiz else "",
                "attempts": [],
            }
        quiz_history[a.quiz_id]["attempts"].append(a)

    quiz_list = []
    grades = []
    for quiz_id, data in quiz_history.items():
        attempts_list = data["attempts"]
        best_attempt = max(attempts_list, key=lambda x: x.pass_count or 0)
        total_attempts = len(attempts_list)
        # Calculate grade as percent correct if possible
        total_questions = (best_attempt.pass_count or 0) + (best_attempt.fail_count or 0)
        grade = (best_attempt.pass_count / total_questions * 100) if total_questions else 0
        grades.append(grade)
        quiz_list.append({
            "quiz_name": data["quiz_name"],
            "date": best_attempt.end_at,
            "grade": f"{grade:.0f}%",
            "retakes": total_attempts - 1,
        })

    avg_quiz_grade = f"{(sum(grades) / len(grades)):.0f}%" if grades else "N/A"

    # 6. Points History (if you have a log, otherwise use quiz completions)
    points_history = [
        {
            "points": a.pass_count,  # or however you award points
            "date": a.end_at,
            "description": f"Quiz {a.quiz.name} Completed"
        }
        for a in attempts if a.pass_count
    ]

    # 7. Achievements
    achievements = user.achievements
    achs = [
        {
            "achievement_id": a.achievement_id, 
            "name": a.achievement.name_en,
            "description": a.achievement.description_en,
            "completed_at": a.completed_at
        } for a in achievements
    ]
    achs = sorted(achs, key=lambda x: x["completed_at"], reverse=True)


    # 8. Assemble response
    return {
        "total_points": points,
        "points_history": points_history,
        "avg_quiz_grade": avg_quiz_grade,
        "quiz_history": quiz_list,
        "badges_earned": badges_earned,
        "badges": badges,
        "learning_streak": streak,
        "achievements": achs, 
        "student_info": {
            "first_name": user.first_name, 
            "last_name": user.last_name, 
            "created_at": user.created_at, 
            "notes": user.notes, 
            "last_login_time": user.last_login_time, 
            "deactivated": user.deactivated, 
            "grade": user.grade
        }
    }

@router.post("/student", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_student(student: StudentCreate,
                         db: Session = Depends(get_db),
                         admin: User = Depends(get_current_admin)): 
    """_summary_ admin will call this route to create a student with 
    1. username
    2. a password
    3. first name 
    4. last name

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
        points=0,
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
    students = db.query(User).join(Points).filter(User.school_id == admin.school_id, User.is_admin == False).all()
    res = {
        s.username: {
            "username": s.username,
            "first_name": s.first_name,
            "last_name": s.last_name,
            "created_at": s.created_at,
            "last_login_time": s.last_login_time,
            "deactivated": s.deactivated,
            "grade": s.grade,
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
    if student_update.school is not None:
        student.school = student_update.school
    if student_update.grade is not None:
        student.grade = student_update.grade
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

@router.get("/contents", response_model=TopicsOut, status_code=status.HTTP_200_OK)
async def get_all_content(
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
   """ return all the topics uploaded from that school

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Returns:
        _type_: _description_
    """
   school_id = admin.school_id
   topics = db.query(Topic).filter(Topic.school_id == school_id).all()
   res = [
       TopicOut(
           topic_id=t.topic_id, 
           topic_name=t.topic_name, 
           state=t.state, 
           week_number=t.week_number, 
           updated_at=t.updated_at
       )
   for t in topics ]
   return TopicsOut(topics=res)


@router.post("/content-upload", response_model=dict, status_code=status.HTTP_200_OK) 
async def content_upload(
    file: UploadFile, 
    title: str = Form(...),
    week_number: int = Form(...),
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
): 
    """upload the pdf file to the s3 bucket and insert the a new topic entry with initial state READY_FOR_GENERATION

    Args:
        file (UploadFile): _description_
        week_number (int): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Returns:
        _type_: _description_
    """
    school_id = admin.school_id
    # stage 1: compute and compare the hash_value of the file to check if it's duplicate 
    contents = await file.read() 
    hashed = hashlib.sha256(contents).hexdigest()
    # check if the hash value is already in the database
    hash_values = db.query(Topic.hash_value).filter(Topic.school_id == school_id).all()
    hash_values_in_db = set(h[0] for h in hash_values)
    if hashed in hash_values_in_db: 
        return {"message": "File might already been uploaded by other admins"}

    # stage 2: upload the file to S3
    s3_url = None
    try:
        s3_url = s3_service.upload_file_to_s3(
            file_content=contents,
            school_id=school_id,
            filename=file.filename,
        )
        
        if not s3_url:
            return {
                "message": "Failed to upload file to S3", 
                "status": "error"
            }
            
    except Exception as e:
        return {
            "message": f"Error during S3 upload: {str(e)}", 
            "status": "error"
        }

    # stage 3: insert the new topic entry into the topics table 
    new_topic = Topic(
        topic_name = title, 
        s3_bucket_url = s3_url, 
        updated_at = datetime.now(), 
        state = "READY_FOR_GENERATION", 
        hash_value = hashed, 
        week_number = week_number, 
        school_id = school_id
    )
    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    # TODO: need to be change to admin.email
    admin_eamil = admin.email
    send_upload_notification(admin_eamil, file.filename)

    return {
        "message": f"File {file.filename} has been successfully uploaded."
    }

@router.post("/content-reupload", response_model=dict, status_code=status.HTTP_200_OK) 
async def content_reupload(
    file: UploadFile, 
    title: str = Form(...),
    week_number: int = Form(...),
    topic_id: int = Form(...),
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
): 
    """re-upload the pdf file to the s3 bucket and insert the a new topic entry with initial state READY_FOR_GENERATION

    Args:
        file (UploadFile): _description_
        week_number (int): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Returns:
        _type_: _description_
    """
    school_id = admin.school_id

    contents = await file.read()
    # stage 1: remove the entry in the DB
    old_topic = db.query(Topic).filter(Topic.topic_id == topic_id).first() 
    
    db.delete(old_topic)
    
    # stage 2: delete the file on S3
    s3_service.delete_file_by_url(old_topic.s3_bucket_url)
    # stage 3: upload the new file on S3
    s3_url = None
    try:
        s3_url = s3_service.upload_file_to_s3(
            file_content=contents,
            school_id=school_id,
            filename=file.filename,
        )
        
        if not s3_url:
            return {
                "message": "Failed to upload file to S3", 
                "status": "error"
            }
            
    except Exception as e:
        return {
            "message": f"Error during S3 upload: {str(e)}", 
            "status": "error"
        }

    # stage 3: insert the new topic entry into the topics table 
    new_topic = Topic(
        topic_name = title, 
        s3_bucket_url = s3_url, 
        updated_at = datetime.now(), 
        state = "READY_FOR_GENERATION", 
        hash_value = hashlib.sha256(contents).hexdigest(), 
        week_number = week_number, 
        school_id = school_id
    )
    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    # TODO: need to be change to admin.email
    admin_eamil = admin.email
    send_upload_notification(admin_eamil, file.filename)

    return {
        "message": f"File {file.filename} has been successfully re-uploaded."
    }