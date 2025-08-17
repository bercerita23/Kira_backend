import asyncio
from sqlalchemy import select
from app.database.db import get_async_db
from app.router.aws_ses import send_ready_notification
from app.model.topics import Topic
from app.model.users import User

async def ready_for_review():
    """
    Scan for VISUALS_GENERATED entries, change the state of one entry to READY_FOR_REVIEW,
    and send email notifications.
    """
    while True:
        try:
            async with get_async_db() as db:
                # Step 1: fetch a single VISUALS_GENERATED entry (FIFO)
                result = await db.execute( 
                    select(Topic)
                    .filter(Topic.state == "VISUALS_GENERATED")
                    .order_by(Topic.updated_at.asc())
                )
                entry = result.scalars().first()

                if entry is None:
                    # nothing to process
                    await asyncio.sleep(30)
                    continue

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

            # sleep a bit before processing the next entry
            await asyncio.sleep(30)

        except Exception as e:
            print(f"Error in ready_for_review task: {e}")
            await asyncio.sleep(30)
