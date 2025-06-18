from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.model import user_model
from app.schema import user_schema

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/", response_model=user_schema.UserListResponse)
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(user_model.User).filter(user_model.User.email.isnot(None)).all()
    return { "Hello From: ": users }
