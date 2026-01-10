from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from uuid import uuid4
from app.model.verification_codes import VerificationCode
from app.model.users import User
from app.router.aws_ses import send_admin_verification_email, send_reset_request_to_admin
from app.router.auth_util import get_password_hash


def request_reset_password_logic(db: Session, request_body) -> dict:
    if request_body.email:  # Admin is trying to reset password
        user = db.query(User).filter(User.email == request_body.email).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        if not user.is_admin and not user.is_super_admin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email-based password reset is only available for administrators"
            )
        code = str(uuid4())[:8]
        expires_at = datetime.now() + timedelta(minutes=180)

        existing_code = db.query(VerificationCode).filter(
            VerificationCode.email == user.email
        ).first()

        if existing_code:
            existing_code.code = code
            existing_code.expires_at = expires_at
        else:
            reset_code_entry = VerificationCode(
                email=user.email,
                code=code,
                expires_at=expires_at
            )
            db.add(reset_code_entry)

        db.commit()
        send_admin_verification_email(user.email, "forgot-password/reset", code, user.first_name)

        return {"message": f"Reset password email sent to {user.email}"}

    else:  # Student is trying to reset password
        student = db.query(User).filter(User.username == request_body.username).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        res = db.query(User).filter(User.school_id == student.school_id, User.is_admin == True).all()
        admin_emails = [r.email for r in res]
        for email in admin_emails:
            send_reset_request_to_admin("login", email, student.username, student.school_id, student.first_name)

        return {"message": f"Reset password email sent"}


def reset_admin_password_logic(db: Session, request) -> dict:
    verification_code = db.query(VerificationCode).filter(
        VerificationCode.email == request.email,
        VerificationCode.code == request.code,
        VerificationCode.expires_at > datetime.now()
    ).first()

    if not verification_code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code expired or incorrect code.")
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    hashed_password = get_password_hash(request.new_password)
    user.hashed_password = hashed_password
    db.delete(verification_code)
    db.commit()

    return {"message": "Password reset successfully"}
