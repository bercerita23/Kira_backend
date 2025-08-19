from fastapi import APIRouter, Depends, status, HTTPException
from dependencies import get_db, get_current_admin
from app.schema.user_schema import ReviewQuestions
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.model.users import User

from typing import Dict, Any

router = APIRouter()

@router.get("/review-questions/{topic_id}", response_model=ReviewQuestions, status_code=status.HTTP_200_OK)
async def get_topic_questions(topic_id : str, db: Session = Depends(get_db),  admin : User = Depends(get_current_admin))-> Dict[str, Any]:
    questions_list = db.execute(
        text("SELECT * FROM questions WHERE topic_id = :topic_id"), 
        {"topic_id": topic_id}
    )

    if  len(questions_list) == 0: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="topic id not found"
            )
    return ReviewQuestions(questions=questions_list)

@router.post("/approve/{topic_id}", status_code=status.HTTP_202_ACCEPTED)
async def approve_topic(topic_id : str, admin : User = Depends(get_current_admin)):
    return