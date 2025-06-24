from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.model.users import User
from app.schema import user_schema

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/", response_model=user_schema.UserListResponse)
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.email.isnot(None)).all()
    return { "Hello From: ": users }
