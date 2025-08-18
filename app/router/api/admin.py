## Fast API Imports
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form
from app.schema.admin_schema import TopicsOut, TopicOut, PasswordResetWithUsername
from app.router.auth_util import get_password_hash
from app.router.dependencies import *
from typing import List

## Database Imports
from app.database import get_db
from sqlalchemy.orm import Session
from app.router.aws_ses import *
from app.router.aws_s3 import *

## Model imports
from app.model.topics import Topic 
from app.model.users import User
from app.model.reference_counts import *

## Python Library Imports
from datetime import datetime




router = APIRouter()
s3_service = S3Service()
    
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

    if referred_entry.count == 0: # delete the entry and delete it in S3
        s3_service = S3Service()
        s3_service.delete_file_by_url(referred_entry.referred_s3_url)
        # delete file on S3 
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
            week_number=week_number
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
        school_id = school_id
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

    admin_eamil = admin.email
    send_upload_notification(admin_eamil, file.filename)

    return {
        "message": f"File {file.filename} has been successfully uploaded."
    }

