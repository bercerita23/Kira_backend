## Fast API imports
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    status, 
    status
    )

## Model Imports 
from app.model.users import User
from app.model.user_badges import UserBadge
from app.model.badges import Badge
from app.model.points import Points
from app.model.streaks import Streak
from app.model.user_achievements import UserAchievement
from app.model.achievements import Achievement

## Databse imports 
from app.database.db import get_db
from sqlalchemy import asc
from sqlalchemy.orm import Session, joinedload
from app.database.session import SQLALCHEMY_DATABASE_URL

# Other imports
from app.schema.user_schema import *
from app.router.dependencies import *

router = APIRouter()

@router.get("/badges/all", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges information in the database."""
    badges = db.query(Badge).all()
    badge_list = [
        {
            "badge_id": b.badge_id,
            "name": b.name,
            "bahasa_indonesia_name": b.bahasa_indonesia_name,
            "bahasa_indonesia_description": b.bahasa_indonesia_description,
            "description": b.description,
            "icon_url": b.icon_url,
            "earned_by_points": b.earned_by_points,
            "points_required": b.points_required
        }
        for b in badges
    ]
    return {"badges": badge_list}

@router.get("/badges", response_model=UserBadgesOut, status_code=status.HTTP_200_OK)
async def get_a_user_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges that a user has earned

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    badges = db.query(UserBadge).options(joinedload(UserBadge.badge)).filter(UserBadge.user_id == user.user_id).all()
    earned_badges = [UserBadgeOut(
            badge_id=b.badge_id,
            earned_at=b.earned_at,
            view_count=b.view_count,
            name=b.badge.name,
            description=b.badge.description,
            icon_url=b.badge.icon_url
        ) for b in badges]
    for b in badges: 
        b.view_count += 1

    db.commit()
    return UserBadgesOut(badges=earned_badges)

@router.get("/badges/notification", response_model=UserBadgesOut, status_code=status.HTTP_200_OK)
async def get_not_viewed_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges that a user has not viewed. ONLY used for notification."""
    badges = db.query(UserBadge).join(Badge).filter(UserBadge.user_id == user.user_id, UserBadge.view_count == 0).all()
    earned_badges = [UserBadgeOut(
        badge_id=b.badge_id,
        earned_at=b.earned_at,
        name=b.badge.name,
        description=b.badge.description,
        icon_url=b.badge.icon_url
    ) for b in badges]
    return UserBadgesOut(badges=earned_badges)

@router.get("/achievements/all", response_model=AchievementsOut, status_code=status.HTTP_200_OK)
async def get_all_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievements information in the database.

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    achievements = db.query(Achievement).order_by(asc(Achievement.points)).all()
    achievement_list = [
        SingleAchievement(
            achievement_id=a.id, 
            name_en=a.name_en, 
            name_ind=a.name_ind, 
            description_en=a.description_en, 
            description_ind=a.description_ind,
            points=a.points
        )
        for a in achievements
    ]
    return AchievementsOut(achievements=achievement_list)

@router.get("/achievements", response_model=UserAchievementsOut, status_code=status.HTTP_200_OK)
async def get_a_user_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievements that a user has unlocked

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    user_achievement = db.query(UserAchievement).join(Achievement).filter(UserAchievement.user_id == user.user_id).all()
    completed_ach = [SingleUserAchievement(
        achievement_id = a.achievement_id,
        name_en = a.achievement.name_en,  
        name_ind = a.achievement.name_ind, 
        description_en = a.achievement.description_en, 
        description_ind = a.achievement.description_ind, 
        points = a.achievement.points, 
        completed_at = a.completed_at, 
        view_count = a.view_count
    ) for a in user_achievement]
    for a in user_achievement: 
        a.view_count += 1
    db.commit()
    return UserAchievementsOut(user_achievements=completed_ach)

@router.get("/achievements/notification", response_model=UserAchievementsOut, status_code=status.HTTP_200_OK)
async def get_not_viewed_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievement that a user has not viewed. ONLY used for notification."""
    ach = db.query(UserAchievement).join(Achievement).filter(UserAchievement.user_id == user.user_id, UserAchievement.view_count == 0).all()
    earned_ach = [SingleUserAchievement(
        achievement_id=a.achievement_id, 
        name_en=a.achievement.name_en, 
        name_ind=a.achievement.name_ind,
        description_en=a.achievement.description_en,
        description_ind=a.achievement.description_ind, 
        points=a.achievement.points,
        completed_at=a.completed_at

    ) for a in ach]
    return UserAchievementsOut(user_achievements=earned_ach)

@router.get("/points", response_model=PointsOut, status_code=status.HTTP_200_OK) 
async def get_points(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """get the points record of the current user

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    points = db.query(Points).filter(Points.user_id == user.user_id).first()
    if not points: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Records not found")
    
    res = PointsOut(
        points = points.points
    )
    return res

@router.get("/streaks", response_model=StreakOut, status_code=status.HTTP_200_OK)
async def get_streak(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """get the streak record of the current user

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    streak = db.query(Streak).filter(Streak.user_id == user.user_id).first()
    if not streak: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Records not found")
    
    res = StreakOut(
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_activity=streak.last_activity
    )
    return res