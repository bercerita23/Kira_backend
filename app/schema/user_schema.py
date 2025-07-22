from pydantic import BaseModel
from typing import Optional, List, Union
from datetime import datetime

class UserOut(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: Optional[str]
    school_id: Optional[int]

class UserListResponse(BaseModel):
    Hello_From: List[UserOut]

class UserBadgeOut(BaseModel):
    badge_id: str
    earned_at: datetime
    is_viewed: bool
    name: str
    description: Union[str, None]
    icon_url: Union[str, None]

class UserBadgesOut(BaseModel):
    badges: List[UserBadgeOut]

class PointsOut(BaseModel): 
    points: int

class StreakOut(BaseModel): 
    current_streak: int
    longest_streak: int
    last_activity: datetime

############
### Quiz ###
############
class Quiz(BaseModel): 
    quiz_id: int 
    school_id: str
    creator_id: str
    name: str
    questions: List[str]
    description: str
    created_at: datetime
    expired_at: datetime
    is_locked: bool

class QuizzesOut(BaseModel): 
    quizzes: List[Quiz]

################
### Question ###
################
class Question(BaseModel): 
    question_id: int
    content: str
    options: List[str]
    question_type: str
    points: int
    answer: str
    image_url: Optional[str] = None

class QuestionsOut(BaseModel): 
    questions: List[Question]

class QuizSubmission(BaseModel):
    quiz_id: int
    pass_count: int
    fail_count: int
    start_at: datetime
    end_at: datetime

class BestAttemptOut(BaseModel):
    quiz_id: int
    pass_count: int
    fail_count: int
    attempt_count: int
    quiz_name: str
    completed_at: datetime

class BestAttemptsOut(BaseModel):
    attempts: List[BestAttemptOut]