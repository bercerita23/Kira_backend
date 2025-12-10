from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr

class Invitation(BaseModel):
    school_id: str
    email: EmailStr
    first_name: str
    last_name: str

class AdminActivation(BaseModel): 
    email: EmailStr

class AdminOut(BaseModel):
    user_id: str
    email: str
    first_name: str
    last_name: str
    last_login_time: datetime | None
    deactivated: bool

    model_config = {
        "from_attributes": True
    }

class SchoolWithAdminsOut(BaseModel):
    school_id: str
    display_id: Optional[str]
    name: str
    email: str
    data_fetched_at: datetime
    admins: List[AdminOut]
    student_count: int

    model_config = {
        "from_attributes": True
    }

class SchoolsResponse(BaseModel):
    schools: List[SchoolWithAdminsOut]

class NewSchool(BaseModel):
    name: str 
    email: str
    address: str
    telephone: str
    max_questions: Optional[int] = None
    question_prompt: Optional[str] = None
    image_prompt: Optional[str] = None
    kira_chat_prompt: Optional[str] = None

    
class UpdateSchool(BaseModel):
    name: str 
    email: str
    address: str
    telephone: str
    school_id: str
    max_questions: Optional[int] = None
    question_prompt: Optional[str] = None
    image_prompt: Optional[str] = None
    kira_chat_prompt: Optional[str] = None
