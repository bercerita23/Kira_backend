from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, Form
from sqlalchemy.orm import Session
from app.database import get_db
from app.schema.admin_schema import *
from app.schema.user_schema import ApproveQuestions
from app.router.auth_util import *
from app.model.users import User
from app.router.dependencies import *
from typing import List, Annotated, Dict, Any
from app.router.api.logics.admin_logic import (
    get_detail_student_info_logic,
    create_student_logic,
    get_students_logic,
    reset_student_password_logic,
    update_student_info_logic,
    deactivate_student_logic,
    reactivate_student_logic,
    get_all_content_logic,
    get_all_hash_logic,
    increase_count_logic,
    decrease_count_logic,
    content_upload_logic,
    content_upload_chunk_logic,
    get_topic_questions_logic,
    approve_topic_logic,
    replace_question_image_logic,
    get_total_time_logic,
    get_mean_scores_logic,
    get_quiz_statistics_logic,
    get_average_time_per_student_per_month_logic,
    generate_unique_user_id
)
from app.schema.user_schema import ReviewQuestions
from app.router.aws_s3 import S3Service
from app.router.aws_ses import *
import os
import tempfile
import shutil

router = APIRouter()
s3_service = S3Service()

@router.get("/student/{username}", response_model=dict, status_code=status.HTTP_200_OK)
async def get_detail_student_info(
    username: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get detailed student information including points, badges, achievements, and quiz performance.
    
    Args:
        username (str): Username of student to get info for
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Comprehensive student information
    """
    return get_detail_student_info_logic(db, username, admin)

@router.post("/student", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_student(student: StudentCreate,
                         db: Session = Depends(get_db),
                         admin: User = Depends(get_current_admin)): 
    """Create a new student in the admin's school.
    
    Args:
        student (StudentCreate): Student creation data
        db (Session): Database session
        admin (User): Current admin user

    Returns:
        dict: Success message with created user_id
    """
    return create_student_logic(db, student, admin)

@router.get("/students", response_model=dict, status_code=status.HTTP_200_OK)
async def get_students(db: Session = Depends(get_db), admin: User = Depends(get_current_admin)): 
    """Get all students in the admin's school.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Dictionary containing student data
    """
    return get_students_logic(db, admin)
    
@router.patch("/reset-pw", response_model=dict, status_code=status.HTTP_200_OK)
async def reset_student_password(request: PasswordResetWithUsername,
                                 db: Session = Depends(get_db), 
                                 admin: User = Depends(get_current_admin)):
    """Reset a student's password by username.
    
    Args:
        request (PasswordResetWithUsername): Contains username and new password
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Success message
    """
    return reset_student_password_logic(db, request, admin)

@router.patch("/update", response_model=dict, status_code=status.HTTP_200_OK)
async def update_student_info(
    student_update: StudentUpdate, 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Update student information.
    
    Args:
        student_update (StudentUpdate): Updated student information
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Success message
    """
    return update_student_info_logic(db, student_update, admin)

@router.patch("/deactivate_student", response_model=dict, status_code=status.HTTP_200_OK)
async def deactivate_student(
    request: StudentDeactivateRequest,
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Deactivate a student.
    
    Args:
        request (StudentDeactivateRequest): Contains username
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Success message
    """
    return deactivate_student_logic(db, request, admin)

@router.patch("/reactivate-student", response_model=dict, status_code=status.HTTP_200_OK)
async def reactivate_student(
    request: StudentReactivateRequest,
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Reactivate a deactivated student.
    
    Args:
        request (StudentReactivateRequest): Contains username
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Success message
    """
    return reactivate_student_logic(db, request, admin)

@router.get("/contents", response_model=TopicsOut, status_code=status.HTTP_200_OK)
async def get_all_content(
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Get all topics uploaded from the admin's school.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        TopicsOut: List of topics for the school
    """
    return get_all_content_logic(db, admin)

@router.get("/hash-values", response_model=List, status_code=status.HTTP_200_OK)
async def get_all_hash(
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
): 
    """Get all file hash values.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        List[str]: List of hash values
    """
    return get_all_hash_logic(db, admin)

@router.post("/upload-content-lite", response_model=dict, status_code=status.HTTP_200_OK)
async def increase_count(
    title: str = Form(...),
    week_number: int = Form(...),
    hash_value: str = Form(...),
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin), 
): 
    """Create a topic using an existing file reference.
    
    Args:
        title (str): Topic title
        week_number (int): Week number
        hash_value (str): Hash of existing file
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Success message
    """
    return increase_count_logic(db, title, week_number, hash_value, admin)


CHUNK_DIR = os.path.join(tempfile.gettempdir(), "chunk_uploads")
os.makedirs(CHUNK_DIR, exist_ok=True)

@router.post("/content-upload-chunk", response_model=dict, status_code=status.HTTP_200_OK)
async def content_upload_chunk(
    file: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    upload_id: str = Form(...),
    filename: str = Form(...),
    title: str = Form(...),
    week_number: int = Form(...),
    hash_value: str = Form(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Handle chunked file upload.
    
    Args:
        file (UploadFile): Chunk file data
        chunk_index (int): Index of this chunk
        total_chunks (int): Total number of chunks
        upload_id (str): Unique upload ID
        filename (str): Original filename
        title (str): Topic title
        week_number (int): Week number
        hash_value (str): Hash value of file
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Status message
    """
    chunk_content = await file.read()
    return content_upload_chunk_logic(
        db, chunk_content, chunk_index, total_chunks,
        upload_id, filename, title, week_number, hash_value, admin, CHUNK_DIR
    )




@router.post("/remove-content", response_model=dict, status_code=status.HTTP_200_OK)
async def decrease_count(
    topic_id: int = Form(...), 
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin)
):
    """Remove content (topic) and decrease reference count.
    
    Args:
        topic_id (int): Topic ID to remove
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Success message
    """
    return decrease_count_logic(db, topic_id, admin)
    
    
@router.post("/content-upload", response_model=dict, status_code=status.HTTP_200_OK) 
async def content_upload(
    file: UploadFile, 
    title: str = Form(...),
    week_number: int = Form(...),
    hash_value: str = Form(...),
    db: Session = Depends(get_db), 
    admin: User = Depends(get_current_admin), 
): 
    """Upload a new file to S3 and create topic/reference count records.
    
    Args:
        file (UploadFile): File to upload
        title (str): Topic title
        week_number (int): Week number
        hash_value (str): Hash value of file
        db (Session): Database session
        admin (User): Current admin user

    Returns:
        dict: Success message
    """
    file_content = await file.read()
    return content_upload_logic(db, file_content, file.filename, title, week_number, hash_value, admin)

@router.get("/review-questions/{topic_id}", response_model=ReviewQuestions, status_code=status.HTTP_200_OK)
async def get_topic_questions(topic_id: int, db: Session = Depends(get_db), admin: User = Depends(get_current_admin)) -> Dict[str, Any]:
    """Get all review questions for a topic.
    
    Args:
        topic_id (int): Topic ID to query
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        ReviewQuestions: Question details for the topic
    """
    return get_topic_questions_logic(db, topic_id, admin)

@router.post("/approve/{topic_id}", status_code=status.HTTP_200_OK)
async def approve_topic(
    topic_id: int, 
    approved_questions: ApproveQuestions, 
    user: User = Depends(get_current_admin), 
    db: Session = Depends(get_db), 
):
    """Approve topic questions and create quizzes.
    
    Args:
        topic_id (int): Topic ID to approve
        approved_questions (ApproveQuestions): Approved questions data
        user (User): Current admin user
        db (Session): Database session
        
    Returns:
        dict: Success message
    """
    return approve_topic_logic(db, topic_id, approved_questions, user)

@router.post("/replace-img/{question_id}", status_code=status.HTTP_200_OK)
async def replace_question_image(
    question_id: int,
    file: UploadFile,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Replace the image for a question.
    
    Args:
        question_id (int): Question ID
        file (UploadFile): New image file
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Success message
    """
    file_content = await file.read()
    return replace_question_image_logic(db, question_id, file_content, file.content_type, admin)

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
    """Get time spent in quizzes and chat sessions for the admin's school.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        dict: Total time in seconds
    """
    return get_total_time_logic(db, admin)


@router.get("/mean-scores", status_code=status.HTTP_200_OK)
async def get_mean_scores(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get average quiz score (latest attempt only) per user.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        List[Dict]: Mean scores for each user
    """
    return get_mean_scores_logic(db, admin)


@router.get("/quiz-stats", status_code=status.HTTP_200_OK)
async def get_quiz_statistics(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get quiz statistics for the admin's school.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        List[Dict]: Quiz statistics
    """
    return get_quiz_statistics_logic(db, admin)


@router.get("/time-stats", status_code=status.HTTP_200_OK)
async def get_average_time_per_student_per_month(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Get average time per student per month.
    
    Args:
        db (Session): Database session
        admin (User): Current admin user
        
    Returns:
        Dict: Average and total time statistics
    """
    return get_average_time_per_student_per_month_logic(db, admin)

