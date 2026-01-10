from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.model.users import User
from app.schema.super_admin_schema import *
from app.router.dependencies import get_current_super_admin
from app.router.api.logics.super_admin_logic import (
    invite_admin_logic,
    deactivate_admin_logic,
    reactivate_admin_logic,
    get_all_users_logic,
    get_schools_with_admins_logic,
    create_new_school_logic,
    delete_school_logic,
    get_inactive_schools_logic,
    activate_school_logic,
    suspend_school_logic,
    update_school_logic,
    get_all_schools_logic,
    get_default_prompts_logic
)

router = APIRouter()


@router.post("/invite", response_model=dict, status_code=status.HTTP_200_OK)
async def invite(
    request: Invitation, db: Session = Depends(get_db), super_admin: User = Depends(get_current_super_admin)
):
    """Super admin will call this endpoint to send an invitation email to a new school admin to register."""
    return invite_admin_logic(db, request)


@router.post("/deactivate_admin", response_model=dict)
async def deactivate_admin(
    request: AdminActivation, 
    db: Session = Depends(get_db), 
    super_admin: User = Depends(get_current_super_admin)
):
    """Deactivate an admin."""
    return deactivate_admin_logic(db, request)


@router.post("/reactivate_admin")
async def reactivate_admin(
    request: AdminActivation, 
    db: Session = Depends(get_db), 
    super_admin: User = Depends(get_current_super_admin)
): 
    """Reactivate an admin."""
    return reactivate_admin_logic(db, request)


@router.get("/")
def get_all_users(
    db: Session = Depends(get_db), 
    super_admin: User = Depends(get_current_super_admin)
):
    """Get all active users."""
    return get_all_users_logic(db)


@router.get("/schools_with_admins", response_model=SchoolsResponse, status_code=status.HTTP_200_OK)
async def get_schools_with_admins(
    db: Session = Depends(get_db), 
    super_admin: User = Depends(get_current_super_admin)
):
    """Enhanced fetch schools with admins."""
    return get_schools_with_admins_logic(db)


@router.post('/addschool', status_code=status.HTTP_201_CREATED)
async def create_new_school(
    new_school: NewSchool,
    db: Session = Depends(get_db),
    user = Depends(get_current_super_admin)
):
    """Create a new school."""
    return create_new_school_logic(db, new_school)


@router.post('/removeschool/{school_id}', status_code=status.HTTP_202_ACCEPTED)
async def delete_school(
    school_id: str, 
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_super_admin)
):
    """Delete (deactivate) a school."""
    return delete_school_logic(db, school_id)


@router.get('/inactiveschools')
async def get_inactive_schools(
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_super_admin)
):
    """Get all inactive or suspended schools."""
    return get_inactive_schools_logic(db)


@router.post("/activateschool/{school_id}", status_code=status.HTTP_202_ACCEPTED)
async def activate_school(
    school_id: str, 
    db: Session = Depends(get_db), 
    user: User = Depends(get_current_super_admin)
):
    """Activate a school."""
    return activate_school_logic(db, school_id)


@router.post("/deleteschool/{school_id}")
def suspend_school(
    school_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin),
):
    """Suspend a school."""
    return suspend_school_logic(db, school_id)


@router.post('/updateschool', status_code=status.HTTP_200_OK)
def update_school(
    updated_school: UpdateSchool,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_super_admin)
):
    """Update a school."""
    return update_school_logic(db, updated_school)


@router.get("/schools", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_school(db: Session = Depends(get_db)):
    """Get all active schools."""
    return get_all_schools_logic(db)


@router.get("/default-prompts", status_code=status.HTTP_200_OK)
def get_default_prompts(super_admin: User = Depends(get_current_super_admin)):
    """Return default prompts for question generation, image generation, and Kira chat.
    Used when creating new schools or when schools don't have custom prompts.
    """
    return get_default_prompts_logic()
