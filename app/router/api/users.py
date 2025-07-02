from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.model.users import User
from app.schema import user_schema
from app.router.dependencies import *
router = APIRouter()

@router.get("/")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return { "Hello_Form:" : users }