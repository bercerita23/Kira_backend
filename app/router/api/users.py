from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.model.users import User
from app.schema import user_schema

router = APIRouter()

@router.get("/")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.email.isnot(None)).all()
    return { "Hello_Form:" : users }
