from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, cast, Date, union_all, select, Float, null, text, desc
from fastapi import HTTPException, status
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import os
import tempfile
import shutil
import random

from app.model.users import User
from app.model.topics import Topic
from app.model.questions import Question as QuestionModel
from app.model.quizzes import Quiz
from app.model.attempts import Attempt
from app.model.chats import ChatSession
from app.model.points import Points
from app.model.reference_counts import ReferenceCount
from app.router.auth_util import get_password_hash, verify_password
from app.router.aws_s3 import S3Service
from app.router.aws_ses import send_upload_notification, send_quiz_published
from app.router.s3_signer import presign_get
from app.schema.admin_schema import (
    TopicsOut, TopicOut, PasswordResetWithUsername,
    StudentCreate, StudentUpdate, StudentDeactivateRequest,
    StudentReactivateRequest
)
from app.schema.user_schema import Question as QuestionSchema, ReviewQuestions, ApproveQuestions
from botocore.exceptions import ClientError, NoCredentialsError


def get_detail_student_info_logic(
    db: Session,
    username: str,
    admin: User
) -> Dict[str, Any]:
    """Get detailed student information including points, badges, achievements, and quiz performance.
    
    Args:
        db (Session): Database session
        username (str): Username of student to get info for
        admin (User): Current admin user
        
    Returns:
        Dict[str, Any]: Comprehensive student information
        
    Raises:
        HTTPException: If student not found in admin's school
    """
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
            "points": a.pass_count,
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


def create_student_logic(
    db: Session,
    student: StudentCreate,
    admin: User
) -> Dict[str, Any]:
    """Create a new student in the admin's school.
    
    Args:
        db (Session): Database session
        student (StudentCreate): Student creation data
        admin (User): Current admin user
        
    Returns:
        Dict[str, Any]: Success message with created user_id
    """
    new_student = User(
        user_id=generate_unique_user_id(db), 
        username=student.username,
        hashed_password=get_password_hash(student.password),
        first_name=student.first_name,
        last_name=student.last_name,
        school_id=admin.school_id, 
        grade=student.grade
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


def get_students_logic(db: Session, admin: User) -> Dict[str, Any]:
    """Get all students in the admin's school.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        Dict[str, Any]: Dictionary containing student data
    """
    students = db.query(User).join(Points).filter(
        User.school_id == admin.school_id,
        User.is_admin == False
    ).all()
    
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
    return {"student_data": res}


def reset_student_password_logic(
    db: Session,
    request: PasswordResetWithUsername,
    admin: User
) -> Dict[str, str]:
    """Reset a student's password by username.
    
    Args:
        db (Session): Database session
        request (PasswordResetWithUsername): Contains username and new password
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If student not found
    """
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password 
    db.commit()

    return {"message": "Password reset successfully"}


def update_student_info_logic(
    db: Session,
    student_update: StudentUpdate,
    admin: User
) -> Dict[str, str]:
    """Update student information.
    
    Args:
        db (Session): Database session
        student_update (StudentUpdate): Updated student information
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If student not found or username already exists
    """
    # Find the student in admin's school using current username
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
    if student_update.new_username is not None:
        student.username = student_update.new_username
    if student_update.school is not None:
        student.school = student_update.school
    if student_update.grade is not None:
        student.grade = student_update.grade
    
    db.commit()
    return {"message": "Student information updated successfully"}


def deactivate_student_logic(
    db: Session,
    request: StudentDeactivateRequest,
    admin: User
) -> Dict[str, str]:
    """Deactivate a student.
    
    Args:
        db (Session): Database session
        request (StudentDeactivateRequest): Contains username
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If student not found or already deactivated
    """
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


def reactivate_student_logic(
    db: Session,
    request: StudentReactivateRequest,
    admin: User
) -> Dict[str, str]:
    """Reactivate a deactivated student.
    
    Args:
        db (Session): Database session
        request (StudentReactivateRequest): Contains username
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If student not found or already active
    """
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


def get_all_content_logic(db: Session, admin: User) -> TopicsOut:
    """Get all topics uploaded from the admin's school.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        TopicsOut: List of topics for the school
    """
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
        for t in topics
    ]
    return TopicsOut(topics=res)


def get_all_hash_logic(db: Session, admin: User) -> List[str]:
    """Get all file hash values.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        List[str]: List of hash values
    """
    temp = db.query(ReferenceCount).all()
    res = [t.hash_value for t in temp]
    return res


def increase_count_logic(
    db: Session,
    title: str,
    week_number: int,
    hash_value: str,
    admin: User
) -> Dict[str, str]:
    """Create a topic using an existing file reference.
    
    Args:
        db (Session): Database session
        title (str): Topic title
        week_number (int): Week number
        hash_value (str): Hash of existing file
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
    """
    entity = db.query(ReferenceCount).filter(ReferenceCount.hash_value == hash_value).first()
    entity.count += 1 

    new_topic = Topic(
        topic_name=title, 
        s3_bucket_url=entity.referred_s3_url, 
        updated_at=datetime.now(), 
        state="READY_FOR_GENERATION", 
        hash_value=hash_value, 
        week_number=week_number, 
        school_id=admin.school_id
    )

    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    send_upload_notification(admin.email, "")
    return {"message": f"File has been successfully uploaded."}


def decrease_count_logic(
    db: Session,
    topic_id: int,
    admin: User
) -> Dict[str, str]:
    """Remove content (topic) and decrease reference count.
    
    Args:
        db (Session): Database session
        topic_id (int): Topic ID to remove
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If deletion fails
    """
    selected_topic = db.query(Topic).filter(Topic.topic_id == topic_id).first()

    s3_url = selected_topic.s3_bucket_url
    referred_entry = db.query(ReferenceCount).filter(ReferenceCount.referred_s3_url == s3_url).first()
    referred_entry.count -= 1

    s3_service = S3Service()
    if referred_entry.count == 0:  # delete the entry and delete it in S3
        s3_service.delete_file_by_url(referred_entry.referred_s3_url) 
        db.delete(referred_entry)
    # delete the topic 
    db.delete(selected_topic)
    db.commit()
    return {"message": "The content has been deleted."}


def content_upload_logic(
    db: Session,
    file_content: bytes,
    filename: str,
    title: str,
    week_number: int,
    hash_value: str,
    admin: User
) -> Dict[str, str]:
    """Upload a new file to S3 and create topic/reference count records.
    
    Args:
        db (Session): Database session
        file_content (bytes): File content to upload
        filename (str): Original filename
        title (str): Topic title
        week_number (int): Week number
        hash_value (str): Hash value of file
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
    """
    school_id = admin.school_id
    s3_service = S3Service()
    
    # Upload the file to S3
    s3_url = None
    try:
        s3_url = s3_service.upload_file_to_s3(
            file_content=file_content,
            school_id=school_id,
            filename=filename,
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

    # Insert the new topic entry and reference count
    new_topic = Topic(
        topic_name=title, 
        s3_bucket_url=s3_url, 
        updated_at=datetime.now(), 
        state="READY_FOR_GENERATION", 
        hash_value=hash_value, 
        week_number=week_number, 
        school_id=school_id, 
        summary=""
    )
    
    new_reference_count = ReferenceCount(
        hash_value=hash_value,
        count=1, 
        referred_s3_url=s3_url
    )
    db.add(new_reference_count)
    db.add(new_topic)
    db.commit()
    db.refresh(new_topic)
    db.refresh(new_reference_count)

    send_upload_notification(admin.email, filename)

    return {"message": f"File {filename} has been successfully upload."}


def content_upload_chunk_logic(
    db: Session,
    chunk_content: bytes,
    chunk_index: int,
    total_chunks: int,
    upload_id: str,
    filename: str,
    title: str,
    week_number: int,
    hash_value: str,
    admin: User,
    chunk_dir: str
) -> Dict[str, Any]:
    """Handle chunked file upload.
    
    Args:
        db (Session): Database session
        chunk_content (bytes): Content of this chunk
        chunk_index (int): Index of this chunk
        total_chunks (int): Total number of chunks
        upload_id (str): Unique upload ID
        filename (str): Original filename
        title (str): Topic title
        week_number (int): Week number
        hash_value (str): Hash value of file
        admin (User): Current admin user
        chunk_dir (str): Directory to store chunks
        
    Returns:
        Dict[str, Any]: Status message
    """
    upload_dir = os.path.join(chunk_dir, upload_id)
    os.makedirs(upload_dir, exist_ok=True)

    chunk_path = os.path.join(upload_dir, f"chunk_{chunk_index}")
    with open(chunk_path, "wb") as f:
        f.write(chunk_content)

    uploaded_chunks = [name for name in os.listdir(upload_dir) if name.startswith("chunk_")]
    if len(uploaded_chunks) == total_chunks:
        assembled_path = os.path.join(upload_dir, filename)
        with open(assembled_path, "wb") as assembled:
            for i in range(total_chunks):
                chunk_file = os.path.join(upload_dir, f"chunk_{i}")
                with open(chunk_file, "rb") as cf:
                    assembled.write(cf.read())
        
        with open(assembled_path, "rb") as f:
            file_content = f.read()
        
        s3_service = S3Service()
        try:
            s3_url = s3_service.upload_file_to_s3(
                file_content=file_content,
                school_id=admin.school_id,
                filename=filename,
                week_number=week_number,
                folder_prefix='content'
            )
            if not s3_url:
                shutil.rmtree(upload_dir, ignore_errors=True)
                return {
                    "message": "Failed to upload file to S3",
                    "status": "error"
                }
        except Exception as e:
            shutil.rmtree(upload_dir, ignore_errors=True)
            return {
                "message": f"Error during S3 upload: {str(e)}",
                "status": "error"
            }

        # Insert Topic and ReferenceCount
        new_topic = Topic(
            topic_name=title,
            s3_bucket_url=s3_url,
            updated_at=datetime.now(),
            state="READY_FOR_GENERATION",
            hash_value=hash_value,
            week_number=week_number,
            school_id=admin.school_id,
            summary=""
        )
        new_reference_count = ReferenceCount(
            hash_value=hash_value,
            count=1,
            referred_s3_url=s3_url
        )
        db.add(new_reference_count)
        db.add(new_topic)
        db.commit()
        db.refresh(new_topic)
        db.refresh(new_reference_count)

        send_upload_notification(admin.email, filename)
        shutil.rmtree(upload_dir, ignore_errors=True)
        return {
            "message": f"File {filename} has been successfully uploaded."
        }

    return {"message": f"Chunk {chunk_index+1}/{total_chunks} uploaded for upload_id {upload_id}."}


def get_topic_questions_logic(
    db: Session,
    topic_id: int,
    admin: User
) -> ReviewQuestions:
    """Get all review questions for a topic.
    
    Args:
        db (Session): Database session
        topic_id (int): Topic ID to query
        admin (User): Current admin user
        
    Returns:
        ReviewQuestions: Question details for the topic
        
    Raises:
        HTTPException: If topic not found
    """
    query_result = db.query(QuestionModel).where(QuestionModel.topic_id == topic_id)
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
        ))

    if len(response_questions) == 0: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="topic id not found"
        )
    
    return ReviewQuestions(
        quiz_name=topic_query[0].topic_name, 
        quiz_description="", 
        questions=response_questions
    )


def approve_topic_logic(
    db: Session,
    topic_id: int,
    approved_questions: ApproveQuestions,
    admin: User
) -> Dict[str, str]:
    """Approve topic questions and create quizzes.
    
    Args:
        db (Session): Database session
        topic_id (int): Topic ID to approve
        approved_questions (ApproveQuestions): Approved questions data
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If topic not found or validation fails
    """
    if not approved_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="no approved questions given"
        )

    query_result = db.query(QuestionModel).where(QuestionModel.topic_id == topic_id).with_for_update()
    questions_list = query_result.all()

    if len(questions_list) == 0: 
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
    
    # Commit changed questions
    db.commit()

    # Create 3 random ordered questions for 3 quizzes.
    for i in range(3):
        randomized_questions = question_id_list[:]
        random.shuffle(randomized_questions)
        new_quiz = Quiz(
            name=f"Quiz {i + 1} - {approved_questions.quiz_name}",
            description=approved_questions.quiz_description, 
            school_id=admin.school_id,
            creator_id=admin.user_id, 
            questions=randomized_questions,
            topic_id=topic_id, 
            expired_at=datetime.now() + timedelta(days=7), 
            created_at=datetime.now(),
            is_locked=False, 
        )

        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)
    
    # After completion, change the status of the topic to DONE.
    topic_query = db.query(Topic).where(Topic.topic_id == topic_id).limit(1).with_for_update().all()
    topic_query[0].state = "DONE"
    db.commit()
    send_quiz_published(admin.email)

    return {"message": f"Topic id {topic_id} has been approved"}


def replace_question_image_logic(
    db: Session,
    question_id: int,
    file_content: bytes,
    content_type: str,
    admin: User
) -> Dict[str, str]:
    """Replace the image for a question.
    
    Args:
        db (Session): Database session
        question_id (int): Question ID
        file_content (bytes): New image file content
        content_type (str): MIME type of image
        admin (User): Current admin user
        
    Returns:
        Dict[str, str]: Success message
        
    Raises:
        HTTPException: If question not found or error replacing image
    """
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
        s3_service = S3Service()
        
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
            ContentType=content_type
        )
        
        return {"message": "Image successfully replaced"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error replacing image: {str(e)}"
        )


def get_total_time_logic(db: Session, admin: User) -> Dict[str, Any]:
    """Get total time spent in quizzes and chat sessions.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        Dict[str, Any]: Total time in seconds
    """
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
        )
    )

    chats_subq = (
        select(
            cast(ChatSession.created_at, Date).label("just_date"),
            (func.extract("epoch", ChatSession.ended_at - ChatSession.created_at)).label("duration_seconds")
        )
        .join(User, User.user_id == ChatSession.user_id)
        .where(
            User.school_id == admin.school_id,
            ChatSession.created_at.isnot(None),
            ChatSession.ended_at.isnot(None)
        )
    )

    combined = union_all(attempts_subq, chats_subq)

    query = select(
        func.sum(combined.selected_columns.duration_seconds).label("total_avg_seconds")
    )

    results = db.execute(query).scalar()
    return {"total_time_seconds": results or 0}


def get_mean_scores_logic(db: Session, admin: User) -> List[Dict[str, Any]]:
    """Get average quiz score (latest attempt only) per user.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        List[Dict[str, Any]]: Mean scores for each user
    """
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


def get_quiz_statistics_logic(db: Session, admin: User) -> List[Dict[str, Any]]:
    """Get quiz statistics for the admin's school.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        List[Dict[str, Any]]: Quiz statistics
    """
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

    completion_expr = func.count(latest_subq.c.user_id).label("completion_count")
    median_expr = func.percentile_cont(0.5).within_group(score_expr).label("median_score")

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


def get_average_time_per_student_per_month_logic(db: Session, admin: User) -> Dict[str, Any]:
    """Get average time per student per month.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        Dict[str, Any]: Average and total time statistics
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


def generate_unique_user_id(db: Session) -> str:
    """Generate a unique user ID.
    
    Args:
        db (Session): Database session
        
    Returns:
        str: Unique user ID
    """
    import uuid
    user_id = str(uuid.uuid4())
    while db.query(User).filter(User.user_id == user_id).first():
        user_id = str(uuid.uuid4())
    return user_id
