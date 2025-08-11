import asyncio
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.model.topics import *
from app.router.aws_ses import *
from app.model.users import *

async def prompt_generation(): 
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)

    while True: 
        try:
            with SessionLocal() as db:
                # find entries that are READY_FOR_GENERATION
                ready_entries = db.query(Topic).filter(Topic.state == "READY_FOR_GENERATION").all()
                
                # get the pdf from S3 

                # quiz and prompt generation 
                
                # change the state to PROMPTS_GENERATED
             
        except Exception as e: 
            print(f"Error in repeated task: {e}")
        finally: 
            db.close()
            await asyncio.sleep(10)

async def visual_generation(): 
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)

    while True: 
        try:
            with SessionLocal as db: 
                # find entries that are PROMPTS_GENERATED
                ready_entries = db.query(Topic).filter(Topic.state == "PROMPTS_GENERATED").all()
                
                # generate the visual 

                # store the visuals either url

                # change the state to VISUALS_GENERATED

            await asyncio.sleep(10) 
        except Exception as e: 
            print(f"Error in repeated task: {e}")
            await asyncio.sleep(10) 

async def ready_for_review():
    """Scan for visuals generated entries, change their state to ready for review and send them email 
    """
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    while True:
        try:
            with SessionLocal() as db:
                # find entries that are VISUALS_GENERATED
                ready_entries = db.query(Topic).filter(Topic.state == "VISUALS_GENERATED").all()

                # change the state to READY_FOR_REVIEW
                for ready_entry in ready_entries:
                    ready_entry.state = "READY_FOR_REVIEW"

                # send admin notification to review
                school_ids = {re.school_id for re in ready_entries}
                if school_ids:
                    admin_emails = (
                        db.query(User.email)
                        .filter(User.is_admin == True, User.school_id.in_(school_ids))
                        .all()
                    )
                    for email in admin_emails:
                        send_ready_notification(email[0])

                db.commit()

            await asyncio.sleep(10)

        except Exception as e:
            print(f"Error in repeated task: {e}")
            # rollback just in case
            try:
                db.rollback()
            except:
                pass
            await asyncio.sleep(10)


# async def hello_world():
#     """Run the repeated task every 10 seconds"""
#     while True:
#         try:
#             print("Hello World every 10 sec")
#             await asyncio.sleep(10)  # 10 seconds for testing
#         except Exception as e:
#             print(f"Error in repeated task: {e}")
#             await asyncio.sleep(10) 
# 
# async def hello_sky():
#     """Run the repeated task every 10 seconds"""
#     while True:
#         try:
#             print("Hello Sky every 5 sec")
#             await asyncio.sleep(5)  # 10 seconds for testing
#         except Exception as e:
#             print(f"Error in repeated task: {e}")
#             await asyncio.sleep(5) 