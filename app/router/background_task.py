from app.model.points import Points
from app.model.user_badges import UserBadge
from app.model.badges import Badge
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from sqlalchemy import func

#############
### Badge ###
#############

def check_and_award_badges(user_id: str):
    """
    Background task to check and award badges to a user based on their points.
    Creates a new DB session for the background task.
    """
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    db = SessionLocal()
    try:
        # Fetch all badge requirements
        badges_info = db.query(Badge.badge_id, Badge.points_required).all()
        badge_info_dict = {info.badge_id: info.points_required for info in badges_info}

        # Fetch user's points
        points_record = db.query(Points).filter(Points.user_id == user_id).first()
        if not points_record:
            return
        user_points = points_record.points

        # Fetch all badges the user already has
        user_badges = db.query(UserBadge.badge_id).filter(UserBadge.user_id == user_id).all()
        user_badge_ids = {ub.badge_id for ub in user_badges}

        # Determine which badges to award
        new_badges = []
        for badge_id, points_required in badge_info_dict.items():
            if user_points >= points_required and badge_id not in user_badge_ids:
                new_badges.append(
                    UserBadge(
                        user_id=user_id,
                        badge_id=badge_id,
                        earned_at=func.now(),
                        is_viewed=False
                    )
                )

        if new_badges:
            db.add_all(new_badges)
            db.commit()
    finally:
        db.close()

