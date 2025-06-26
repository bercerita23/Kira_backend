from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from datetime import datetime

router = APIRouter()

@router.get("/", response_model=dict, status_code=status.HTTP_200_OK)
async def get_verification_code(email: str = Query(...), db: Session = Depends(get_db)):
    """_summary_

    Args:
        email (str, optional): _description_. Defaults to Query(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """

    result = db.execute(
        text("SELECT * FROM verification_codes WHERE email = :email"),
        {"email": email}

    ).fetchone()
    if not result:
        raise HTTPException(status_code=404, detail="Verification code not found, please try again!")
    if result.expires_at < datetime.now(): 
        raise HTTPException(status_code=400, detail="Expired verification code")
    
    return {"email": result.email,"code": result.code,"expires_at": result.expires_at.isoformat()}

@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def delete_verification_code(email: str = Query(...), db: Session = Depends(get_db)):
    """_summary_

    Args:
        email (str, optional): _description_. Defaults to Query(...).
        db (Session, optional): _description_. Defaults to Depends(get_db).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    # Delete verification code entry from verification_code table
    # Return verification entry by email from verification_code table
    result = db.execute(
        text("DELETE FROM verification_codes WHERE email = :email"),
        {"email": email}
    )
    db.commit()
    
    return {"message": "Verification code deleted successfully"}