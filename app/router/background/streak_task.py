from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.model.streaks import Streak
from app.model.attempts import Attempt


##############
### streak ###
##############

def update_streak(user_id: str):
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    db: Session = SessionLocal()

    try:
        now = datetime.utcnow()
        today = now.date()
        yesterday = today - timedelta(days=1)

        # Check if the user already made an attempt today
        today_attempt = db.query(Attempt).filter(
            Attempt.user_id == user_id,
            Attempt.end_at >= datetime.combine(today, datetime.min.time()),
            Attempt.end_at <= datetime.combine(today, datetime.max.time())
        ).first()

        if not today_attempt:
            return  # No attempt today, nothing to update

        # Fetch or create streak
        streak = db.query(Streak).filter(Streak.user_id == user_id).first()
        if not streak:
            streak = Streak(
                user_id=user_id,
                current_streak=1,
                longest_streak=1,
                last_activity=now
            )
            db.add(streak)
            db.commit()
            return

        last_date = streak.last_activity.date() if streak.last_activity else None

        if last_date == today:
            return  # Already updated today

        if last_date == yesterday:
            streak.current_streak += 1
        else:
            streak.current_streak = 1

        streak.longest_streak = max(streak.longest_streak, streak.current_streak)
        streak.last_activity = now
        streak.updated_at = now
        db.commit()

    finally:
        db.close()
