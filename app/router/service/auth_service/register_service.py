from datetime import timedelta, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import uuid4
from app.model.verification_codes import VerificationCode
from app.model.temp_admins import TempAdmin
from app.model.users import User
from app.router.auth_util import get_password_hash
from app.router.aws_ses import send_admin_verification_email
from app.model.schools import School, SchoolStatus


def register_admin_logic(db: Session, request) -> dict:
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == request.email,
        VerificationCode.code == request.code,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Either the verification code has expired, or an incorrect one was inputted. Please check again")

    temp_admin = db.query(TempAdmin).filter(TempAdmin.email == request.email).first()
    if not temp_admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invitation not found.")

    if (request.school_id != temp_admin.school_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect school was chosen")
    if (request.first_name != temp_admin.first_name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect First Name was inputted")
    if (request.last_name != temp_admin.last_name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect Last Name was inputted")

    admin = User(
        user_id=temp_admin.user_id,
        school_id=temp_admin.school_id,
        email=temp_admin.email,
        hashed_password=get_password_hash(request.password),
        first_name=temp_admin.first_name,
        last_name=temp_admin.last_name,
        created_at=datetime.now(),
        is_super_admin=False,
        is_admin=True,
        username=None,
        deactivated=False
    )

    temp_admin.verified = True

    db.add(admin)
    db.delete(verification_code)
    db.commit()
    return {"message": "You have been registered successfully."}


def resend_verification_logic(db: Session, request) -> dict:
    # First check: Is this for registration? (unverified temp admin)
    temp_admin = db.query(TempAdmin).filter(
        TempAdmin.email == request.email,
        TempAdmin.verified == False
    ).first()

    if temp_admin:
        # Generate new code for registration
        code = str(uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=180)

        existing_code = db.query(VerificationCode).filter(
            VerificationCode.email == request.email
        ).first()

        if existing_code:
            existing_code.code = code
            existing_code.expires_at = expires_at
        else:
            verification_code = VerificationCode(
                email=request.email,
                code=code,
                expires_at=expires_at
            )
            db.add(verification_code)

        db.commit()
        send_admin_verification_email(request.email, "register-admin", code, temp_admin.first_name)
        return {"message": f"Registration verification code resent to {request.email}"}

    # Second check: Is this for password reset? (existing admin user)
    user = db.query(User).filter(User.email == request.email).first()

    if user and (user.is_admin or user.is_super_admin):
        # Generate new code for password reset
        code = str(uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=180)

        existing_code = db.query(VerificationCode).filter(
            VerificationCode.email == request.email
        ).first()

        if existing_code:
            existing_code.code = code
            existing_code.expires_at = expires_at
        else:
            verification_code = VerificationCode(
                email=request.email,
                code=code,
                expires_at=expires_at
            )
            db.add(verification_code)

        db.commit()
        send_admin_verification_email(request.email, "forgot-password/reset", code, user.first_name)
        return {"message": f"Password reset verification code resent to {request.email}"}

    # Email not found in either scenario
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No pending registration or password reset found for this email"
    )


def get_all_school_logic(db: Session) -> dict:
    temp = db.query(School).filter(School.status == SchoolStatus.active).all()
    res = [{
        "school_id": school.school_id,
        "name": school.name,
        "status": school.status.value,
    } for school in temp]
    return {"schools": res}
