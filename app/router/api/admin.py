from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy.orm import aliased
from sqlalchemy.sql import label, literal_column
from sqlalchemy import case, desc
from app.database import get_db
from app.schema.admin_schema import *
from app.schema.user_schema import ApproveQuestions
from app.router.auth_util import *
from app.model.topics import Topic 
from app.model.questions import Question as QuestionModel
from app.model.quizzes import Quiz
from app.model.chats import ChatSession
from app.model.attempts import Attempt
from app.model.users import User
from app.model.reference_counts import *
from app.router.dependencies import *
from typing import List, Annotated
from datetime import datetime
from app.model.points import Points
from sqlalchemy import func, cast, Date, union_all, select, Float, null, text
import hashlib
import boto3
from typing import Optional
from botocore.exceptions import ClientError, NoCredentialsError
from app.router.aws_s3 import *
from app.router.aws_ses import *
import fitz 
from app.schema.user_schema import Question as QuestionSchema, ReviewQuestions
from app.router.s3_signer import presign_get
from datetime import datetime, timedelta
import random
from app.router.aws_s3 import *
#test

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
        school_id=admin.school_id, 
        grade= student.grade
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
    """_summary_: Update student information (first_name, last_name, email, notes, username)
    
    Args:
        student_update (StudentUpdate): Updated student information
        db (Session): Database session
        admin (User): Current admin user
        
    Raises:
        HTTPException: If student not found or not in admin's school
        
    Returns:
        dict: Success message
    """
    # Find the student in admin's school using current username
    student = db.query(User).filter(
        User.username == student_update.username,  # Use current username to find
        User.school_id == admin.school_id,
        User.is_admin == False
    ).first()
    
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Student not found in your school"
        )
    
    # Check if new username already exists (if updating username)
    if student_update.new_username is not None and student_update.new_username != student_update.username:
        existing_user = db.query(User).filter(User.username == student_update.new_username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already exists"
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
    if student_update.new_username is not None:  # Use new_username field
        student.username = student_update.new_username
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
   import os
   from urllib.parse import urlparse
   school_id = admin.school_id
   topics = db.query(Topic).filter(Topic.school_id == school_id).all()
   res = [
       TopicOut(
           topic_id=t.topic_id, 
           topic_name=t.topic_name, 
           state=t.state, 
           week_number=t.week_number, 
           updated_at=t.updated_at,
           file_name=os.path.basename(urlparse(t.s3_bucket_url).path) if t.s3_bucket_url else ""
       )
   for t in topics ]
   return TopicsOut(topics=res)

@router.get("/hash-values", response_model=List, status_code=status.HTTP_200_OK)
async def get_all_hash(
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
): 
    """return a list of file hash, can be empty

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        admin (User, optional): _description_. Defaults to Depends(get_current_admin).

    Returns:
        _type_: _description_
    """
    temp = db.query(ReferenceCount).all()
    res = [t.hash_value for t in temp]

    return res

@router.post("/upload-content-lite", response_model=dict, status_code=status.HTTP_200_OK)
async def increase_count(
    title: str = Form(...),
    week_number: int = Form(...),
    hash_value: str = Form(...),
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin), 
): 
    """_summary_

    Args:
        title (str, optional): _description_. Defaults to Form(...).
        week_number (int, optional): _description_. Defaults to Form(...).
        hash_value (str, optional): The hash value of the file. Defaults to Form(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).
        admin (User, optional): _description_. Defaults to Depends(get_current_admin).

    Returns:
        _type_: _description_
    """
    entity = db.query(ReferenceCount).filter(ReferenceCount.hash_value == hash_value).first()
    entity.count += 1 

    new_topic = Topic(
        topic_name = title, 
        s3_bucket_url = entity.referred_s3_url, 
        updated_at = datetime.now(), 
        state = "READY_FOR_GENERATION", 
        hash_value = hash_value, 
        week_number = week_number, 
        school_id = admin.school_id
    )

    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    send_upload_notification(admin.email, "")
    return {
        "message": f"File has been successfully uploaded."
    }

@router.post("/remove-content", response_model=dict, status_code=status.HTTP_200_OK)
async def decrease_count(
    topic_id: int = Form(...), 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Decrease reference count for a topic and optionally delete S3 file if no longer referenced

    Args:
        topic_id (int): The ID of the topic to delete
        db (Session): Database session
        admin (User): Current authenticated admin user

    Returns:
        dict: Success/error message

    Raises:
        HTTPException: If topic not found or deletion fails
    """
    selected_topic = db.query(Topic).filter(Topic.topic_id == topic_id).first()

    s3_url = selected_topic.s3_bucket_url
    referred_entry = db.query(ReferenceCount).filter(ReferenceCount.referred_s3_url == s3_url).first()
    referred_entry.count -= 1

    s3_service = S3Service()
    if referred_entry.count == 0: # delete the entry and delete it in S3
        s3_service.delete_file_by_url(referred_entry.referred_s3_url) 
        db.delete(referred_entry)
    # delete the topic 
    db.delete(selected_topic)
    db.commit()
    return {"message": "The content has been deleted."}
    
    
@router.post("/content-upload", response_model=dict, status_code=status.HTTP_200_OK) 
async def content_upload(
    file: UploadFile, 
    title: str = Form(...),
    week_number: int = Form(...),
    hash_value: str = Form(...),
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin), 
): 
    """upload a new file that doesn't exist

    Args:
        file (UploadFile): _description_
        title (str, optional): _description_. Defaults to Form(...).
        week_number (int, optional): _description_. Defaults to Form(...).
        hash_value (str, optional): the hash value of the file from the frontend. Defaults to Form(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).
        admin (User, optional): _description_. Defaults to Depends(get_current_admin).

    Returns:
        _type_: _description_
    """
    school_id = admin.school_id
    contents = await file.read() 
    # stage 2: upload the file to S3
    s3_url = None
    try:
        s3_url = s3_service.upload_file_to_s3(
            file_content=contents,
            school_id=school_id,
            filename=file.filename,
            week_number=week_number,
            folder_prefix='content'
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
        hash_value = hash_value, 
        week_number = week_number, 
        school_id = school_id, 
        summary = ""
    )
    
    new_reference_count = ReferenceCount(
        hash_value = hash_value,
        count = 1, 
        referred_s3_url = s3_url
    )
    db.add(new_reference_count)
    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    db.refresh(new_reference_count)

    admin_email = admin.email
    send_upload_notification(admin_email, file.filename)

    return {
        "message": f"File {file.filename} has been successfully uploaded."
    }

@router.get("/review-questions/{topic_id}", response_model=ReviewQuestions, status_code=status.HTTP_200_OK)
async def get_topic_questions(topic_id : int, db: Session = Depends(get_db),  admin : User = Depends(get_current_admin))-> Dict[str, Any]:
    '''
        get all review questions with the same topic_id

        args: 
            topic_id : topic Id being querried
            db (Session, optional): _description_. Defaults to Depends(get_db).
            admin (User, optional): _description_. Defaults to Depends(get_current_admin).
        Returns:

    '''
    query_result= db.query(QuestionModel).where(QuestionModel.topic_id == topic_id)
    topic_query = db.query(Topic).where(Topic.topic_id == topic_id).limit(1).all()
    questions_list = query_result.all()

    response_questions: List[QuestionSchema] = []
    for question in questions_list: 
        signed_url = presign_get(question.image_url)
        response_questions.append(QuestionSchema(
            question_id=question.question_id,
            content=question.content,
            options=question.options,
            question_type=question.question_type,
            points=question.points,
            answer=question.answer,
            image_url=signed_url
            )
        )

    if  len(response_questions) == 0: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="topic id not found"
            )
    return ReviewQuestions (
        quiz_name = topic_query[0].topic_name, 
        quiz_description = "", 
        questions = response_questions
        )

@router.post("/approve/{topic_id}", status_code=status.HTTP_200_OK)
async def approve_topic(
    topic_id : int, 
    approved_questions: ApproveQuestions, 
    user : User = Depends(get_current_admin), 
    db: Session = Depends(get_db), 
    ):
    if not approved_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="no approved questions given"
        )
    '''
        Approve topic questions based on topic_id. 
        
        args:
            topic_id : topic Id being approved
            approved_questions : a list of approved questions 
            db (Session, optional): _description_. Defaults to Depends(get_db).
            admin (User, optional): _description_. Defaults to Depends(get_current_admin).
            
        Returns:
            _type_: _description_

    '''
    query_result= db.query(QuestionModel).where(QuestionModel.topic_id == topic_id).with_for_update()
    questions_list = query_result.all()

    if  len(questions_list) == 0: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="topic id not found"
            )
    if len(questions_list) != len(approved_questions.questions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="approved questions do not match topic ID"
        )
    
    question_id_list = []
    
    # Only update changed and changeable fields
    for approved_question in approved_questions.questions:
        for question in questions_list:
            if question.question_id == approved_question.question_id:
                question_id_list.append(question.question_id)
                if question.answer != approved_question.answer:
                    question.answer = approved_question.answer
                if question.content != approved_question.content:
                    question.content = approved_question.content
                if question.options != approved_question.options:
                    question.options = approved_question.options
    # Commit changed 
    db.commit()

    # Create 3 random ordered questions for 3 quizes.
    for i in range(3) :
        randomized_questions = question_id_list[:]
        random.shuffle(randomized_questions)
        new_quiz = Quiz(
            name = f"Quiz {i + 1} - {approved_questions.quiz_name}",
            description = approved_questions.quiz_description, 
            school_id = user.school_id,
            creator_id = user.user_id, 
            questions = randomized_questions,
            topic_id = topic_id, 
            expired_at = datetime.now() + timedelta(days=7), 
            created_at = datetime.now(),
            is_locked = False, 
        )

        # Add the new quiz, commit and insert automated fields.
        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)
    
    # After completion, change the status of the topic to DONE. 
    topic_query = db.query(Topic).where(Topic.topic_id == topic_id).limit(1).with_for_update().all()
    topic_query[0].state = "DONE"
    db.commit()
    send_quiz_published(user.email)

    return {"message" : f"Topic id {topic_id} has been approved"}

@router.post("/replace-img/{question_id}", status_code=status.HTTP_200_OK)
async def replace_question_image(
    question_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Replace the existing image for a question with a new one.
    The new image will be uploaded to the same S3 location, effectively replacing the old one.
    """
    # Find the question
    question = db.query(QuestionModel).filter(
        QuestionModel.question_id == question_id,
        QuestionModel.school_id == admin.school_id
    ).first()
    
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found or does not belong to your school"
        )
    
    if not question.image_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This question does not have an existing image"
        )
        
    try:
        # Read file content
        file_content = await file.read()
        
        # Extract the existing S3 key from the URL
        s3_key = s3_service._extract_key_from_url(question.image_url)
        if not s3_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid S3 URL format in database"
            )
            
        # Upload new file with same key (this will replace the existing file)
        s3_service.s3_client.put_object(
            Bucket=s3_service.bucket_name,
            Key=s3_key,
            Body=file_content,
            ContentType=file.content_type
        )
        
        return {"message": "Image successfully replaced"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error replacing image: {str(e)}"
        )

# @router.get("/content-url/{quiz_id}", response_model=dict, status_code=status.HTTP_200_OK)
# async def get_question_content_url(
#     quiz_id: int,
#     db: Session = Depends(get_db),
#     #admin: User = Depends(get_current_admin)
# ):
#     """Get the content URL for a specific question."""
#     quiz = db.query(Quiz).filter(
#         Quiz.quiz_id == quiz_id
#     ).first()
# 
#     topic_url = db.query(Topic.s3_bucket_url).filter(Topic.topic_id == quiz.topic_id).first()
#     if not topic_url:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Content not found"
#         )
# 
#     return {"content_url": topic_url[0]}

# total time spent on quizzes and chat sessions per day for the admin's school
@router.get("/time-spent", status_code=status.HTTP_200_OK)
async def get_total_time(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)):
    """Get time spent in quizzes/chat sessions for the admin's school."""

    attempts_subq = (
    select(
        cast(Attempt.start_at, Date).label("just_date"),
        (func.extract("epoch", Attempt.end_at - Attempt.start_at)).label("duration_seconds")
    )
    .join(Quiz, Quiz.quiz_id == Attempt.quiz_id)
    .where(
        Quiz.school_id == admin.school_id,  
        Attempt.start_at.isnot(None),
        Attempt.end_at.isnot(None)
    ))

    chats_subq = (
        select(
            cast(ChatSession.created_at, Date).label("just_date"),
            (func.extract("epoch", ChatSession.ended_at - ChatSession.created_at)).label("duration_seconds")
        ).join(User, User.user_id == ChatSession.user_id)
        .where(User.school_id == admin.school_id, ChatSession.created_at.isnot(None), ChatSession.ended_at.isnot(None))
    )

    combined = union_all(attempts_subq, chats_subq)

    query = select(
        func.sum(combined.selected_columns.duration_seconds).label("total_avg_seconds")
    )

    results = db.execute(query).scalar()
    return {"total_time_seconds": results or 0}


@router.get("/quizzes", status_code=status.HTTP_200_OK)
async def get_total_time(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)):
    """Get time spent in quizzes/chat sessions for the admin's school."""

    attempts_subq = (
    select(
        cast(Attempt.start_at, Date).label("just_date"),
        (func.extract("epoch", Attempt.end_at - Attempt.start_at)).label("duration_seconds")
    )
    .join(Quiz, Quiz.quiz_id == Attempt.quiz_id)
    .where(
        Quiz.school_id == admin.school_id,  
        Attempt.start_at.isnot(None),
        Attempt.end_at.isnot(None)
    ))

    chats_subq = (
        select(
            cast(ChatSession.created_at, Date).label("just_date"),
            (func.extract("epoch", ChatSession.ended_at - ChatSession.created_at)).label("duration_seconds")
        ).join(User, User.user_id == ChatSession.user_id)
        .where(User.school_id == admin.school_id, ChatSession.created_at.isnot(None), ChatSession.ended_at.isnot(None))
    )

    combined = union_all(attempts_subq, chats_subq)

    query = select(
        func.sum(combined.selected_columns.duration_seconds).label("total_avg_seconds")
    )

    results = db.execute(query).scalar()
    return {"total_time_seconds": results or 0}


@router.get("/mean-scores", status_code=status.HTTP_200_OK)
async def get_mean_scores(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Compute average quiz score (latest attempt only) per user in admin's school."""

    latest_subq = (
        select(
            Attempt.attempt_id,
            Attempt.quiz_id,
            Attempt.user_id,
            Attempt.pass_count,
            Attempt.fail_count,
            func.row_number()
                .over(
                    partition_by=[Attempt.quiz_id, Attempt.user_id],
                    order_by=desc(Attempt.attempt_number)
                )
                .label("rn")
        )
        .join(Quiz, Quiz.quiz_id == Attempt.quiz_id)
        .where(Quiz.school_id == admin.school_id)
        .subquery()
    )

    query = (
        select(
            User.user_id,
            User.first_name,
            User.username,
            func.avg(
                cast(
                    (latest_subq.c.pass_count) / 
                    func.nullif(latest_subq.c.pass_count + latest_subq.c.fail_count, 0),
                    Float
                )
            ).label("mean_score")
        )
        .join(User, User.user_id == latest_subq.c.user_id)
        .where(latest_subq.c.rn == 1)
        .group_by(User.user_id, User.first_name, User.username)
        .order_by(desc("mean_score"))
    )

    results = db.execute(query).fetchall()

    return [
        {
            "user_id": row.user_id,
            "first_name": row.first_name,
            "username": row.username,
            "mean_score": float(row.mean_score) if row.mean_score is not None else 0.0
        }
        for row in results
    ]


@router.get("/quiz-stats", status_code=status.HTTP_200_OK)
async def get_quiz_statistics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    latest_subq = (
        select(
            Attempt.quiz_id,
            Attempt.user_id,
            Attempt.pass_count,
            Attempt.fail_count,
            func.row_number()
                .over(
                    partition_by=[Attempt.quiz_id, Attempt.user_id],
                    order_by=desc(Attempt.attempt_number)
                )
                .label("rn")
        )
        .join(Quiz, Quiz.quiz_id == Attempt.quiz_id)
        .where(Quiz.school_id == admin.school_id)
        .subquery()
    )

    score_expr = cast(
        latest_subq.c.pass_count /
        func.nullif(latest_subq.c.pass_count + latest_subq.c.fail_count, 0),
        Float
    )

    completion_expr = func.count(latest_subq.c.user_id).label("completion_count")  # added
    median_expr = func.percentile_cont(0.5).within_group(score_expr).label("median_score")  # added


    query = (
        select(
            latest_subq.c.quiz_id,
            Quiz.name.label("quiz_name"),
            func.avg(score_expr).label("mean_score"),
            func.min(score_expr).label("min_score"),
            func.max(score_expr).label("max_score"),
            func.stddev(score_expr).label("stddev_score"),
            median_expr,
            completion_expr,
            func.array_agg(score_expr).label("scores")
        )
        .join(Quiz, Quiz.quiz_id == latest_subq.c.quiz_id)
        .where(latest_subq.c.rn == 1)
        .group_by(latest_subq.c.quiz_id, Quiz.name, Quiz.created_at)
        .order_by(Quiz.created_at.asc())
    )

    results = db.execute(query).fetchall()

    return [
        {
            "quiz_id": row.quiz_id,
            "quiz_name": row.quiz_name,
            "mean_score": float(row.mean_score) if row.mean_score is not None else 0.0,
            "min_score": float(row.min_score) if row.min_score is not None else 0.0,
            "max_score": float(row.max_score) if row.max_score is not None else 0.0,
            "median_score": float(row.median_score) if row.median_score is not None else 0.0, 
            "completion": int(row.completion_count) if hasattr(row, "completion_count") else 0,
            "stddev_score": float(row.stddev_score) if row.stddev_score is not None else 0.0,
            "scores": [float(s) for s in (row.scores or [])],

        }
        for row in results
    ]

@router.get("/time-stats", status_code=status.HTTP_200_OK)
async def get_average_time_per_student_per_month(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """
    Compute one overall number:
    average time (in minutes) per student per month 
    combining quizzes and Kira chat sessions for the admin's school.
    """

    attempts_subq = (
        select(
            Attempt.user_id.label("user_id"),
            func.date_trunc("month", Attempt.start_at).label("month_start"),
            (func.extract("epoch", Attempt.end_at - Attempt.start_at) / 60.0).label("duration_minutes")
        )
        .join(Quiz, Quiz.quiz_id == Attempt.quiz_id)
        .where(
            Quiz.school_id == admin.school_id,
            Attempt.start_at.isnot(None),
            Attempt.end_at.isnot(None)
        )
    )

    chats_subq = (
        select(
            ChatSession.user_id.label("user_id"),
            func.date_trunc("month", ChatSession.created_at).label("month_start"),
            (func.extract("epoch", ChatSession.ended_at - ChatSession.created_at) / 60.0).label("duration_minutes")
        )
        .join(User, User.user_id == ChatSession.user_id)
        .where(
            User.school_id == admin.school_id,
            ChatSession.created_at.isnot(None),
            ChatSession.ended_at.isnot(None)
        )
    )

    combined = union_all(attempts_subq, chats_subq).subquery()
    total_minutes = db.execute(select(func.sum(combined.c.duration_minutes))).scalar() or 0

    student_count = db.execute(select(func.count(func.distinct(combined.c.user_id)))).scalar() or 0
    month_count = db.execute(select(func.count(func.distinct(combined.c.month_start)))).scalar() or 0
    avg_per_student_per_month = (
        total_minutes / (student_count * month_count)
        if student_count > 0 and month_count > 0
        else 0.0
    )

    return {
        "avg_student_per_month": round(avg_per_student_per_month, 2),
        "total_minutes": round(total_minutes, 2),
    }

