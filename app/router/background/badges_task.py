from sqlalchemy import select
from app.model.points import Points
from app.model.user_badges import UserBadge
from app.model.badges import Badge
from app.model.achievements import *
from app.model.user_achievements import *
from app.model.attempts import *
from app.database.db import get_async_db
from app.database.session import SQLALCHEMY_DATABASE_URL
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

#############
### Badge ###
#############

async def check_and_award_badges(user_id: str):
    """
    Background task to check and award badges to a user based on their points.
    Uses async DB session for better connection management.
    """
    async with get_async_db() as db:
        try:
            # Fetch all badge requirements
            badges_info = await db.execute(select(Badge.badge_id, Badge.points_required))
            badge_info_dict = {info[0]: info[1] for info in badges_info.all()}

            # Fetch user's points
            points_result = await db.execute(
                select(Points).filter(Points.user_id == user_id)
            )
            points_record = points_result.scalar_one_or_none()
            if not points_record:
                return
            user_points = points_record.points

            # Fetch all badges the user already has
            user_badges_result = await db.execute(
                select(UserBadge.badge_id).filter(UserBadge.user_id == user_id)
            )
            user_badge_ids = {ub[0] for ub in user_badges_result.all()}

            # Determine which badges to award
            new_badges = []
            for badge_id, points_required in badge_info_dict.items():
                if user_points >= points_required and badge_id not in user_badge_ids:
                    new_badges.append(
                        UserBadge(
                            user_id=user_id,
                            badge_id=badge_id,
                            earned_at=func.now(),
                            view_count=0
                        )
                    )

            if new_badges:
                db.add_all(new_badges)
                db.commit()
        except Exception as e:
            # Log the error but don't re-raise to prevent breaking the background task
            print(f"Error checking badges for user {user_id}: {e}")

