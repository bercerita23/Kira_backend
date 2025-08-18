## Router Imports
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from app.router.dependencies import get_current_user, get_db
from app.router.background.achievement_task import check_achievement_and_award
from app.router.background.badges_task import check_and_award_badges

## Database Imports 
from sqlalchemy.orm import Session, joinedload
from app.database.session import SQLALCHEMY_DATABASE_URL

## Schema Imports
from app.schema.user_schema import QuizzesOut, Quiz, QuestionsOut, Question, BestAttemptsOut, BestAttemptOut, QuizSubmission

## Model imports
from app.model import quizzes, questions
from app.model.attempts import Attempt
from app.model.points import Points
from app.model.users import User

from .users import router

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

@router.get("/attempts", status_code=status.HTTP_200_OK, response_model=BestAttemptsOut)
async def get_attempts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempts = db.query(Attempt).options(joinedload(Attempt.quiz)).filter(Attempt.user_id == user.user_id).all()
    quiz_attempts = {} # ket= quiz_id, value= list of attempt object

    for attempt in attempts:
        qid = int(attempt.quiz_id)
        if qid not in quiz_attempts:
            quiz_attempts[qid] = []
        quiz_attempts[qid].append(attempt)

    best_attempts = []
    for qid, attempt_list in quiz_attempts.items():
        best_attempt = max(attempt_list, key=lambda x: x.pass_count or 0)
        quiz_name = best_attempt.quiz.name if best_attempt.quiz else ""
        duration_in_sec = int((best_attempt.end_at - best_attempt.start_at).total_seconds())
        best_attempts.append(BestAttemptOut(
            quiz_id=qid,
            pass_count=best_attempt.pass_count or 0,
            fail_count=best_attempt.fail_count or 0,
            attempt_count=len(attempt_list),
            quiz_name=quiz_name,
            duration_in_sec=duration_in_sec,
            completed_at=best_attempt.end_at
        ))

    return BestAttemptsOut(attempts=best_attempts)

@router.post("/submit-quiz", status_code=status.HTTP_201_CREATED)
async def submit_quiz(
    submission: QuizSubmission,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # 1. Get all previous attempts for this user and quiz
    attempts = (
        db.query(Attempt)
        .filter(
            Attempt.user_id == user.user_id,
            Attempt.quiz_id == submission.quiz_id
        )
        .order_by(Attempt.attempt_number.asc())
        .all()
    )
    if len(attempts) >= 2:
        raise HTTPException(status_code=400, detail="Maximum number of attempts reached for this quiz.")

    # Calculate previous best pass_count from attempts
    previous_best_pass = 0
    for a in attempts:
        pass_count = int(a.pass_count) if a.pass_count else 0
        previous_best_pass = max(previous_best_pass, pass_count)
    
    new_pass_count = submission.pass_count
    new_fail_count = submission.fail_count
    
    # Calculate points gained based on improvement in pass_count
    points_gained = max(0, new_pass_count - previous_best_pass)

    # 2. Ensure user's Points record exists and update points if needed
    points_record = db.query(Points).filter(Points.user_id == user.user_id).first()
    if points_gained > 0:
        points_record.points += points_gained

    # 3. Store Attempt
    new_attempt = Attempt(
        user_id=user.user_id,
        quiz_id=submission.quiz_id,
        attempt_number=len(attempts) + 1,
        pass_count=new_pass_count,
        fail_count=new_fail_count,
        start_at=submission.start_at,
        end_at=submission.end_at
    )
    db.add(new_attempt)
    db.commit()
    db.refresh(new_attempt)
    db.refresh(points_record)

    #######################
    ### Background Task ###
    #######################
    background_tasks.add_task(check_achievement_and_award, user.user_id)
    background_tasks.add_task(check_and_award_badges, user.user_id)
    # background_tasks.add_task(update_streak, user.user_id)

    # 5. Prepare response using Pydantic model for serialization
    return {
        "message": "Quiz result submitted."
    }