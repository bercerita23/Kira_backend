from fastapi import APIRouter, Depends, HTTPException, status, Query, status
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.model.users import User
from app.schema.user_schema import *
from app.router.dependencies import *
from app.router.dependencies import get_current_user
from app.database.db import get_db
from app.model.user_badges import UserBadge
from app.model.badges import Badge
from app.model.points import Points
from app.model.streaks import Streak
from app.model import quizzes
from app.model import questions
from sqlalchemy import func


router = APIRouter()

@router.get("/badges", response_model=UserBadgesOut, status_code=status.HTTP_200_OK)
async def get_a_user_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges that a user has earned

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    badges = db.query(UserBadge).options(joinedload(UserBadge.badge)).filter(UserBadge.user_id == user.user_id).all()
    earned_badges = [UserBadgeOut(
            badge_id=b.badge_id,
            earned_at=b.earned_at,
            is_viewed=b.is_viewed,
            name=b.badge.name,
            description=b.badge.description,
            icon_url=b.badge.icon_url
        ) for b in badges]
    
    return UserBadgesOut(badges=earned_badges)

@router.get("/points", response_model=PointsOut, status_code=status.HTTP_200_OK) 
async def get_points(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """get the points record of the current user

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    points = db.query(Points).filter(Points.user_id == user.user_id).first()
    if not points: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Records not found")
    
    res = PointsOut(
        points = points.points
    )
    return res

@router.get("/streaks", response_model=StreakOut, status_code=status.HTTP_200_OK)
async def get_streak(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """get the streak record of the current user

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    streak = db.query(Streak).filter(Streak.user_id == user.user_id).first()
    if not streak: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Records not found")
    
    res = StreakOut(
        current_streak=streak.current_streak,
        longest_streak=streak.longest_streak,
        last_activity=streak.last_activity
    )
    return res

@router.get("/quizzes", 
            response_model=QuizzesOut, 
            status_code=status.HTTP_200_OK)
async def get_quizzes(db: Session = Depends(get_db), 
                      user: User = Depends(get_current_user)):
    """return all the quizzes that belongs to the current user's school

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    temp = db.query(quizzes.Quiz).filter(quizzes.Quiz.school_id == user.school_id).all()
    res = QuizzesOut(
        quizzes=[
            Quiz(
                quiz_id=q.quiz_id,
                school_id=q.school_id,
                creator_id=q.creator_id,
                name=q.name,
                questions=q.questions, 
                description=q.description,
                created_at=q.created_at,
                expired_at=q.expired_at,
                is_locked=q.is_locked
            )
            for q in temp
        ]
    )
    return res

@router.get("/questions/{quiz_id}", 
            response_model=QuestionsOut, # TODO: change to designated schema
            status_code=status.HTTP_200_OK)
async def get_questions(quiz_id: str, 
                        db: Session = Depends(get_db), 
                        user: User = Depends(get_current_user)):
    """return all the questions that belongs to the quiz

    Args:
        quiz_id (str): _description_
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Raises:
        HTTPException: _description_

    Returns:
        _type_: _description_
    """
    temp = db.query(quizzes.Quiz).filter(quizzes.Quiz.quiz_id == int(quiz_id)).first()
    if not temp: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    
    # Fetch all questions in one query
    question_ids = [int(qid) for qid in temp.questions]
    question_objs = db.query(questions.Question).filter(questions.Question.question_id.in_(question_ids)).all()
    question_map = {q.question_id: q for q in question_objs}
    
    # Preserve the order of questions as in temp.questions
    res = []
    for qid in question_ids:
        question = question_map.get(qid)
        if question:
            res.append(Question(
                question_id=question.question_id,
                content=question.content,
                options=question.options,
                question_type=question.question_type,
                points=question.points,
                answer=question.answer,
                image_url=question.image_url
            ))
    return QuestionsOut(questions=res)

@router.post("/submit-quiz", status_code=status.HTTP_201_CREATED)
async def submit_quiz(
    submission: QuizSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Submit a quiz attempt, record score and duration, increment streak if first attempt today.
    """
    # 1. Determine attempt number
    last_attempt = (
        db.query(quizzes.Attempt)
        .filter(
            quizzes.Attempt.user_id == user.user_id,
            quizzes.Attempt.quiz_id == submission.quiz_id
        )
        .order_by(quizzes.Attempt.attempt_number.desc())
        .first()
    )
    attempt_number = 1 if not last_attempt else last_attempt.attempt_number + 1

    # 2. Check if this is the first attempt today (for streaks)
    today = func.date(func.now())
    first_today = not db.query(quizzes.Attempt).filter(
        quizzes.Attempt.user_id == user.user_id,
        func.date(quizzes.Attempt.attempted_at) == today
    ).first()

    # 3. If first attempt today, increment streak
    streak = db.query(Streak).filter(Streak.user_id == user.user_id).first()
    if first_today:
        if streak:
            streak.current_streak += 1
            streak.last_activity = func.now()
        else:
            streak = Streak(user_id=user.user_id, current_streak=1, longest_streak=1, last_activity=func.now())
            db.add(streak)
        db.commit()

    # 4. Store Attempt
    new_attempt = quizzes.Attempt(
        user_id=user.user_id,
        quiz_id=submission.quiz_id,
        score=submission.score,
        attempt_number=attempt_number,
        attempted_at=func.now()
        # duration=submission.duration  # Do not store duration
    )
    db.add(new_attempt)
    db.commit()
    db.refresh(new_attempt)

    # 5. Prepare response
    return {
        "attempt": {
            "attempt_id": new_attempt.attempt_id,
            "quiz_id": new_attempt.quiz_id,
            "score": new_attempt.score,
            "attempt_number": new_attempt.attempt_number,
            "attempted_at": str(new_attempt.attempted_at),
            "duration": new_attempt.duration
        },
        "streak": {
            "current_streak": streak.current_streak if streak else 1,
            "last_activity": str(streak.last_activity) if streak else None
        }
    }
