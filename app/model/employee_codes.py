from sqlalchemy import Column, PrimaryKeyConstraint, String, Boolean
from app.database.base_class import Base

class EmployeeCode(Base):
    __tablename__ = "employee_codes"

    is_super_admin = Column(Boolean, nullable=False)
    code = Column(String(8), nullable=False, primary_key=True, index=True)

