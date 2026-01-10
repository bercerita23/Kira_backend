from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.model.users import User
from app.schema.user_schema import *
from app.router.dependencies import get_current_user
from app.router.api.logics.user_logic import (
    get_all_badges_logic,
    get_user_badges_logic,
    get_not_viewed_badges_logic,
    get_all_achievements_logic,
    get_user_achievements_logic,
    get_not_viewed_achievements_logic,
    get_points_logic,
    get_streak_logic,
    get_quizzes_logic,
    get_questions_logic,
    get_attempts_logic,
    get_all_attempts_logic,
    submit_quiz_logic,
    start_chat_logic,
    send_message_logic,
    end_chat_logic,
    chat_eligibility_logic,
    get_user_details_logic
)
from app.router.background.badges_task import check_and_award_badges
from app.router.background.achievement_task import check_achievement_and_award
from pydantic import BaseModel

router = APIRouter()

# Request schemas
class ChatStartRequest(BaseModel):
    quiz_id: int

class ChatSendRequest(BaseModel):
    session_id: int
    message: str

class ChatEndRequest(BaseModel):
    session_id: int


@router.get("/badges/all", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges information in the database."""
    return get_all_badges_logic(db)


@router.get("/badges", response_model=UserBadgesOut, status_code=status.HTTP_200_OK)
async def get_a_user_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges that a user has earned."""
    return get_user_badges_logic(db, user)


@router.get("/badges/notification", response_model=UserBadgesOut, status_code=status.HTTP_200_OK)
async def get_not_viewed_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges that a user has not viewed. ONLY used for notification."""
    return get_not_viewed_badges_logic(db, user)


@router.get("/achievements/all", response_model=AchievementsOut, status_code=status.HTTP_200_OK)
async def get_all_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievements information in the database."""
    return get_all_achievements_logic(db)


@router.get("/achievements", response_model=UserAchievementsOut, status_code=status.HTTP_200_OK)
async def get_a_user_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievements that a user has unlocked."""
    return get_user_achievements_logic(db, user)


@router.get("/achievements/notification", response_model=UserAchievementsOut, status_code=status.HTTP_200_OK)
async def get_not_viewed_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievement that a user has not viewed. ONLY used for notification."""
    return get_not_viewed_achievements_logic(db, user)


@router.get("/points", response_model=PointsOut, status_code=status.HTTP_200_OK) 
async def get_points(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get the points record of the current user."""
    return get_points_logic(db, user)


@router.get("/streaks", response_model=StreakOut, status_code=status.HTTP_200_OK)
async def get_streak(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get the streak record of the current user."""
    return get_streak_logic(db, user)


@router.get("/quizzes", response_model=QuizzesOut, status_code=status.HTTP_200_OK)
async def get_quizzes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return all the quizzes that belongs to the current user's school."""
    return get_quizzes_logic(db, user)


@router.get("/questions/{quiz_id}", response_model=QuestionsOut, status_code=status.HTTP_200_OK)
async def get_questions(quiz_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Return all the questions that belongs to the quiz."""
    return get_questions_logic(db, quiz_id, user)


@router.get("/attempts", status_code=status.HTTP_200_OK, response_model=BestAttemptsOut)
async def get_attempts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get best attempts for each quiz."""
    return get_attempts_logic(db, user)


@router.post("/submit-quiz", status_code=status.HTTP_201_CREATED)
async def submit_quiz(
    submission: QuizSubmission,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Submit quiz results and trigger background reward processing."""
    result = submit_quiz_logic(db, user, submission)
    
    # Background Task for rewards
    saved_uid = user.user_id
    async def process_rewards(uid):
        try:
            await check_achievement_and_award(uid)
            await check_and_award_badges(uid)
        except Exception as e:
            print(f"Error processing rewards for user {uid}: {e}")
    
    background_tasks.add_task(process_rewards, saved_uid)
    
    return result


@router.post("/chat/start")
async def start_chat(
    request: ChatStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Start a new chat session for a quiz."""
    return start_chat_logic(db, user, request.quiz_id)


@router.post("/chat/send")
async def send_message(
    request: ChatSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Send a message in a chat session."""
    return send_message_logic(db, user, request.session_id, request.message)


@router.post("/chat/end")
async def end_chat(
    request: ChatEndRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """End a chat session."""
    return end_chat_logic(db, user, request.session_id)


@router.get("/chat/eligibility")
async def chat_eligibility(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Check chat eligibility for the user."""
    return chat_eligibility_logic(db, user)


@router.get("/attempts/all", status_code=status.HTTP_200_OK, response_model=BestAttemptsOut) 
async def get_all_attempts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all attempts for each quiz."""
    return get_all_attempts_logic(db, user)


@router.get("/details", status_code=status.HTTP_200_OK, response_model=UserOut)
async def get_user_details(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get user details."""
    return get_user_details_logic(db, user)
