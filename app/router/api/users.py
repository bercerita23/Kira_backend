from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.model.users import User
from app.schema import user_schema

router = APIRouter()

@router.get("/")
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).filter(User.email.isnot(None)).all()
    return { "Hello_Form:" : users }

@router.get("/user-temp", response_model=dict, status_code=status.HTTP_200_OK)
async def check_user_info(email: str = Query(...), db: Session = Depends(get_db)):
    """_summary_ fetch the information that was entered by the admin when inviting a new school admin for the frontend to do the conparision. 

    Args:
        email (str, optional): _description_. Defaults to Query(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    user = db.query(User).filter(User.email == email).first()
    if not user: 
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )   
    
    return {"email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "school_id": user.school_id,
            "user_id": user.user_id}