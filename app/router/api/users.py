from fastapi import APIRouter, Depends, HTTPException, status, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.model.users import User
from app.schema.user_schema import *
from app.router.dependencies import *
from app.router.dependencies import get_current_user
from app.database.db import get_db
from app.model.user_badges import UserBadge
from app.model.badges import Badge


router = APIRouter()

@router.get("/", response_model=UserBadgesOut, status_code=status.HTTP_200_OK)
async def get_a_user_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    
    badges = db.query(UserBadge).filter(UserBadge.user_id == user.user_id).all()
    earned_badges = []
    for badge in badges:
        badge_info = db.query(Badge).filter(Badge.badge_id == badge.badge_id).first()
        earned_badge = UserBadgeOut(
            badge_id=badge.badge_id,
            earned_at=badge.earned_at,
            is_viewed=badge.is_viewed,
            name=badge_info.name,
            description=badge_info.description,
            icon_url=badge_info.icon_url
        )
        earned_badges.append(earned_badge)
    return UserBadgesOut(badges=earned_badges)
