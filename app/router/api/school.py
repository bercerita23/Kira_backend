
from fastapi import APIRouter, Depends, HTTPException, status
from app.database.db import get_db
from sqlalchemy.orm import Session
from app.model.schools import School

router = APIRouter()


@router.get("/", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_school(db: Session = Depends(get_db)):
    
    temp = db.query(School).all()
    res = [{"school_id": school.school_id, "name": school.name, "email": school.email, "address": school.address, "telephone": school.telephone} for school in temp]
    return { "schools": res }
