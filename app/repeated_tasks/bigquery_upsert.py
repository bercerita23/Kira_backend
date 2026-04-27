from datetime import datetime

from google.cloud import bigquery
from sqlalchemy.dialects.postgresql import insert

from app.database.db import SessionLocal
from app.model.analytics import Analytics


def bigquery_nightly_upsert():
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
