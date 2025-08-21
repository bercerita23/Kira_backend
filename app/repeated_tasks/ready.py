import asyncio
from sqlalchemy import select
from app.database.db import get_async_db
from app.router.aws_ses import send_ready_notification
from app.model.topics import Topic
from app.model.users import User

async def ready_for_review():
    """
    Process one VISUALS_GENERATED entry, change its state to READY_FOR_REVIEW,
    and send email notifications.
    """
    async with get_async_db() as db:
        try:
            # Step 1: fetch a single VISUALS_GENERATED entry (FIFO)
            result = await db.execute( 
                select(Topic)
                .filter(Topic.state == "VISUALS_GENERATED")
                .order_by(Topic.updated_at.asc())
            )
            entry = result.scalars().first()

            if entry is None:
                # nothing to process
                return

            # Step 2: change the state
            entry.state = "READY_FOR_REVIEW"

            # Step 3: send admin notifications
            result = await db.execute(
                select(User.email)
                .filter(User.is_admin == True, User.school_id == entry.school_id)
            )
            admin_emails = [row[0] for row in result.all()]
            for email in admin_emails:
                print(f"Notification sent to {email}")
                send_ready_notification(email)

            # Step 4: commit changes
            await db.commit()
            return  # Task completed successfully

        except Exception as e:
            print(f"Error in ready_for_review task: {e}")
            await db.rollback()
            raise  # Let the outer loop handle the error
