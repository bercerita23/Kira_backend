import asyncio
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database.session import get_local_session, SQLALCHEMY_DATABASE_URL

SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL) 

async def cleanup_verification_codes():
    while True:
        await asyncio.sleep(300)  
        db: Session = SessionLocal()  
        try:
            db.execute(text("DELETE FROM verification_code WHERE expires_at < NOW()"))
            db.commit()
        finally:
            db.close()
