
from app.celery_app import celery_app
# import asyncio
# import time
# from app.repeated_tasks.question_and_prompt import prompt_generation
# from app.repeated_tasks.visuals import visual_generation
# from app.repeated_tasks.ready import ready_for_review
from google.cloud import bigquery
from sqlalchemy.dialects.postgresql import insert
from app.model.analytics import Analytics
from app.database.db import SessionLocal
from datetime import datetime


# @celery_app.task(bind=True)
# def worker_loop(self):
#     print("[Celery] Worker loop started.", flush=True)
#     while True:
#         try:
#             print("[Celery] Running prompt_generation...", flush=True)
#             asyncio.run(prompt_generation())
#         except Exception as e:
#             print(f"[Celery] Error in prompt_generation: {e}", flush=True)
#         try:
#             print("[Celery] Running visual_generation...", flush=True)
#             asyncio.run(visual_generation())
#         except Exception as e:
#             print(f"[Celery] Error in visual_generation: {e}", flush=True)
#         try:
#             print("[Celery] Running ready_for_review...", flush=True)
#             asyncio.run(ready_for_review())
#         except Exception as e:
#             print(f"[Celery] Error in ready_for_review: {e}", flush=True)
#         time.sleep(15)

        

@celery_app.task(bind=True)
def bigquery_nightly_upsert(self):

    client = bigquery.Client(project="analytics-482304")
    query = """
    SELECT
        user_id,
        user_ltv.engagement_time_millis AS total_engagement_time_ms,
        last_updated_date
    FROM `analytics_516824409.users_*`
    WHERE _TABLE_SUFFIX = (
    SELECT MAX(_TABLE_SUFFIX)
    FROM `analytics_516824409.users_*`
    WHERE _TABLE_SUFFIX < FORMAT_DATE('%Y%m%d', CURRENT_DATE())
    )"""

    job = client.query(query)
    rows = job.result()

    db = SessionLocal()
    try:
        for row in rows:
            last_updated = (
                datetime.strptime(row.last_updated_date, "%Y%m%d")
                if row.last_updated_date
                else None
            )
            stmt = (
                insert(Analytics)
                .values(
                    user_id=row.user_id,
                    engagement_time_ms=row.total_engagement_time_ms,
                    last_updated=last_updated,
                )
                .on_conflict_do_update(
                    index_elements=["user_id"],
                    set_={
                        "engagement_time_ms": row.total_engagement_time_ms,
                        "last_updated": last_updated,
                    },
                )
            )
            db.execute(stmt)

        db.commit()
        print("Rows successfully inserted.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
