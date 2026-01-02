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
from app.model.attempts import *
from app.model.user_achievements import *
from app.model.achievements import *
from app.model.schools import School
from sqlalchemy import func, asc, desc, null
from fastapi import BackgroundTasks
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from app.router.background.badges_task import check_and_award_badges
from app.router.background.achievement_task import check_achievement_and_award
from app.router.s3_signer import presign_get
from datetime import datetime, timedelta

#chatbot
from app.model.chats import ChatSession, ChatMessage
from app.model.topics import Topic
from app.router.aws_s3 import S3Service
from openai import OpenAI
import io
from app.config import settings
import fitz, io, base64
from pydantic import BaseModel
import re


router = APIRouter()

s3_service = S3Service()
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Add request schema for chat start
class ChatStartRequest(BaseModel):
    quiz_id: int

# Add request schema for chat send
class ChatSendRequest(BaseModel):
    session_id: int
    message: str


@router.get("/badges/all", response_model=dict, status_code=status.HTTP_200_OK)
async def get_all_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges information in the database."""
    badges = db.query(Badge).all()
    badge_list = [
        {
            "badge_id": b.badge_id,
            "name": b.name,
            "bahasa_indonesia_name": b.bahasa_indonesia_name,
            "bahasa_indonesia_description": b.bahasa_indonesia_description,
            "description": b.description,
            "icon_url": b.icon_url,
            "earned_by_points": b.earned_by_points,
            "points_required": b.points_required
        }
        for b in badges
    ]
    return {"badges": badge_list}

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
            view_count=b.view_count,
            name=b.badge.name,
            description=b.badge.description,
            icon_url=b.badge.icon_url
        ) for b in badges]
    for b in badges: 
        b.view_count += 1

    db.commit()
    return UserBadgesOut(badges=earned_badges)

@router.get("/badges/notification", response_model=UserBadgesOut, status_code=status.HTTP_200_OK)
async def get_not_viewed_badges(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the badges that a user has not viewed. ONLY used for notification."""
    badges = db.query(UserBadge).join(Badge).filter(UserBadge.user_id == user.user_id, UserBadge.view_count == 0).all()
    earned_badges = [UserBadgeOut(
        badge_id=b.badge_id,
        earned_at=b.earned_at,
        name=b.badge.name,
        description=b.badge.description,
        icon_url=b.badge.icon_url
    ) for b in badges]
    return UserBadgesOut(badges=earned_badges)

@router.get("/achievements/all", response_model=AchievementsOut, status_code=status.HTTP_200_OK)
async def get_all_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievements information in the database.

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    achievements = db.query(Achievement).order_by(asc(Achievement.points)).all()
    achievement_list = [
        SingleAchievement(
            achievement_id=a.id, 
            name_en=a.name_en, 
            name_ind=a.name_ind, 
            description_en=a.description_en, 
            description_ind=a.description_ind,
            points=a.points
        )
        for a in achievements
    ]
    return AchievementsOut(achievements=achievement_list)

@router.get("/achievements", response_model=UserAchievementsOut, status_code=status.HTTP_200_OK)
async def get_a_user_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievements that a user has unlocked

    Args:
        db (Session, optional): _description_. Defaults to Depends(get_db).
        user (User, optional): _description_. Defaults to Depends(get_current_user).

    Returns:
        _type_: _description_
    """
    user_achievement = db.query(UserAchievement).join(Achievement).filter(UserAchievement.user_id == user.user_id).all()
    completed_ach = [SingleUserAchievement(
        achievement_id = a.achievement_id,
        name_en = a.achievement.name_en,  
        name_ind = a.achievement.name_ind, 
        description_en = a.achievement.description_en, 
        description_ind = a.achievement.description_ind, 
        points = a.achievement.points, 
        completed_at = a.completed_at, 
        view_count = a.view_count
    ) for a in user_achievement]
    for a in user_achievement: 
        a.view_count += 1
    db.commit()
    return UserAchievementsOut(user_achievements=completed_ach)

@router.get("/achievements/notification", response_model=UserAchievementsOut, status_code=status.HTTP_200_OK)
async def get_not_viewed_achievements(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Get all the achievement that a user has not viewed. ONLY used for notification."""
    ach = db.query(UserAchievement).join(Achievement).filter(UserAchievement.user_id == user.user_id, UserAchievement.view_count == 0).all()
    earned_ach = [SingleUserAchievement(
        achievement_id=a.achievement_id, 
        name_en=a.achievement.name_en, 
        name_ind=a.achievement.name_ind,
        description_en=a.achievement.description_en,
        description_ind=a.achievement.description_ind, 
        points=a.achievement.points,
        completed_at=a.completed_at

    ) for a in ach]
    return UserAchievementsOut(user_achievements=earned_ach)

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
            signed_url = presign_get(question.image_url, expires_in=600)
            res.append(Question(
                question_id=question.question_id,
                content=question.content,
                options=question.options,
                question_type=question.question_type,
                points=question.points,
                answer=question.answer,
                image_url=signed_url,
                cloud_front_url=question.cloud_front_url
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
    
    saved_uid = user.user_id
    async def process_rewards(uid):
        try:
            await check_achievement_and_award(uid)
            await check_and_award_badges(uid)
        except Exception as e:
            print(f"Error processing rewards for user {uid}: {e}")
    
    background_tasks.add_task(process_rewards, saved_uid)
    # background_tasks.add_task(update_streak, user.user_id)

    # 5. Prepare response using Pydantic model for serialization
    return {
        "message": "Quiz result submitted."
    }

@router.post("/chat/start")
async def start_chat(
    request: ChatStartRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Find quiz by id for the user's school

    quiz = db.query(quizzes.Quiz).filter(
        quizzes.Quiz.quiz_id == request.quiz_id,
        quizzes.Quiz.school_id == user.school_id
    ).first()

    user_name = user.first_name 
    if user.last_name: 
        user_name += user.last_name

    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    if not quiz.topic_id:
        raise HTTPException(status_code=400, detail="Quiz has no associated topic")
    
    # Find topic for topic summary
    topic = db.query(Topic).filter(Topic.topic_id == quiz.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    
    # Check for recent session (optional - you may want to remove this)
    five_seconds_ago = datetime.now() - timedelta(seconds=5)
    recent_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.user_id == user.user_id,
            ChatSession.created_at >= five_seconds_ago
        )
        .first()
    )

    if recent_session:
        # Instead of blocking, return the existing session
        return {
            "session_id": recent_session.id, 
            "topic_id": quiz.topic_id, 
            "quiz_id": request.quiz_id,
            "message": "Using existing recent session"
        }

    # Create new session with context from topic summary

    # add user_name to the new chat session db
    session = ChatSession(
        user_name=user_name,
        user_id=user.user_id,
        turn_count=0,
        context_text=topic.summary if topic.summary else "No context available"
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return {"session_id": session.id, "topic_id": quiz.topic_id, "quiz_id": request.quiz_id}


@router.post("/chat/send")
async def send_message(
    request: ChatSendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    session = db.query(ChatSession).filter_by(id=request.session_id, user_id=user.user_id).first()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get school information for kira_chat_prompt
    school = db.query(School).filter(School.school_id == user.school_id).first()
    
    if not school:
        raise HTTPException(status_code=404, detail="School not found")

    # increment turn count
    session.turn_count += 1
    db.commit()

    #pick up username from session, and pass it. 
    user_name = session.user_name

    # language stage logic
    if session.turn_count <= 2:
        lang_rule = "Respond only in Bahasa Indonesia."
    elif session.turn_count <= 3:
        lang_rule = "Respond 70% in Bahasa Indonesia, 30% in English (ex: Saya baik, terima kasih! How are you today?)"
    elif session.turn_count <= 4:
        lang_rule = "Respond 50% in Bahasa Indonesia, 50% in English (ex: Mungkin jalan-jalan ke mall, and after that nonton movie with friends)"
    elif session.turn_count <= 6:
        lang_rule = "Respond 30% in Bahasa Indonesia, 70% in English."
    else:
        lang_rule = "Respond fully in English."

    # Use school-specific chat prompt or fallback to default
    if school.kira_chat_prompt:
        system_message = school.kira_chat_prompt + f"Keep your answers very short (1–2 sentences). Use this context:\n{session.context_text} as this is what the class is learning for the week. Keep every answer strictly under 20 words. if user response is not related to the context reply kindly and warmly, and guide them to the topic being discussed. it is currently the {session.turn_count} turn you have talked to the client,  Keep conversations simple, and under 20 words. If its your first time, greet them. You should guide the student to ask questions, if they are not, ask them questions. Keep them engaged"
    else:
        # Default chat prompt
        base_system_prompt = "You are Kira, an english tutor for indonesian students. you can also be refered to as Kira Monkey and you also respond if they are trying to greet you or asking hows is your day."
        system_message = f"{base_system_prompt}. The user's name is: {"John Doe"} be personal. This is the material they are learning this week:\n{session.context_text}. Keep every answer strictly under 20 words. Ask them questions, keep them engaged. if user response is not related to the context reply kindly and warmly, and guide them to the topic being discussed. it is currently the {session.turn_count} time you have talked to the child, as the session progresses, begin using some english, with the goal at the 6th turn, the conversation MUST BE FULLY in english. If the user respond in english, reply in english as well. Keep conversations simple, and under 20 words. If its your first time, greet them in indonesian. It is important for you to {lang_rule}"

    
    # Build the full system message
    

    history_rows = db.query(ChatMessage).filter(ChatMessage.session_id==request.session_id).order_by(ChatMessage.created_at.asc()).all()
    messages = [
        {"role": "system", "content": system_message},
    ]
    messages.extend({"role": r.role, "content": r.content} for r in history_rows)
    messages.append({"role": "user", "content": request.message + lang_rule})


    completion = client.chat.completions.create(
        model="gpt-3.5-turbo",  
        messages=messages
    )

    reply = completion.choices[0].message.content

    # save conversation history
    db.add(ChatMessage(session_id=session.id, role="user", content=request.message))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=reply))
    db.commit()

    return {"reply": reply, "turn_count": session.turn_count}


class ChatEndRequest(BaseModel):
    session_id: int

@router.post("/chat/end")
async def end_chat(
    request: ChatEndRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # 1. Find the session
    session = db.query(ChatSession).filter_by(id=request.session_id, user_id=user.user_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 2. If already ended, return info
    if session.ended_at:
        return {
            "session_id": session.id,
            "user_id": session.user_id,
            "created_at": session.created_at,
            "ended_at": session.ended_at,
            "duration_minutes": session.duration_minutes()
        }

    # 3. Mark as ended
    session.ended_at = datetime.now()
    db.commit()
    db.refresh(session)

    # 4. Return session info
    return {
        "session_id": session.id,
        "user_id": session.user_id,
        "created_at": session.created_at,
        "ended_at": session.ended_at,
        "duration_minutes": session.duration_minutes()
    }



@router.get("/chat/eligibility")
async def chat_eligibility(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())

    # Find previous sessions. 
    last_session = (
          db.query(ChatSession).filter(
          ChatSession.user_id == user.user_id,
          ChatSession.created_at >= start_of_week,
          ChatSession.ended_at.isnot(None),
            )
            .order_by(ChatSession.ended_at.desc())
            .first()
    )
    if last_session and last_session.ended_at:
        recent_attempt = db.query(Attempt).order_by(desc(Attempt.end_at)).filter(Attempt.user_id == user.user_id, Attempt.end_at > last_session.ended_at).order_by(Attempt.end_at.desc()).first()
    elif last_session : 
        recent_attempt = db.query(Attempt).order_by(desc(Attempt.end_at)).filter(Attempt.user_id == user.user_id, Attempt.end_at > last_session.created_at).order_by(Attempt.end_at.desc()).first()
    else :
        recent_attempt = db.query(Attempt).order_by(desc(Attempt.end_at)).filter(Attempt.user_id == user.user_id).order_by(Attempt.end_at.desc()).first()


    if not last_session and recent_attempt:
        return {
            "chat_unlocked": True,
            "recent_quiz": recent_attempt.quiz_id,
            "minutes_used": 0,
            "minutes_remaining": 60
        } 
    

    total_minutes = 0
    
    if not recent_attempt:
        return {
            "chat_unlocked": False,
            "minutes_remaining": 0
        }
    else: 
        return {
            "chat_unlocked": True,
            "recent_quiz": recent_attempt.quiz_id,
            "minutes_used": total_minutes,
            "minutes_remaining": 60
        } 

@router.get("/attempts/all", status_code=status.HTTP_200_OK, response_model=BestAttemptsOut) 
async def get_attempts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    attempts = db.query(Attempt).options(joinedload(Attempt.quiz)).filter(Attempt.user_id == user.user_id).all()
    quiz_attempts = {} # ket= quiz_id, value= list of attempt object

    for attempt in attempts:
        qid = int(attempt.quiz_id)
        if qid not in quiz_attempts:
            quiz_attempts[qid] = []
        quiz_attempts[qid].append(attempt)

    all_attempts = []
    for qid, attempt_list in quiz_attempts.items():
        for attempt in attempt_list:
            quiz_name = attempt.quiz.name if attempt.quiz else ""
            duration_in_sec = int((attempt.end_at - attempt.start_at).total_seconds())
            all_attempts.append(BestAttemptOut(
                quiz_id=qid,
                pass_count=attempt.pass_count or 0,
                fail_count=attempt.fail_count or 0,
                attempt_count=len(attempt_list),
                quiz_name=quiz_name,
                duration_in_sec=duration_in_sec,
                completed_at=attempt.end_at
            ))
    return BestAttemptsOut(attempts=all_attempts)

@router.get("/details", status_code=status.HTTP_200_OK, response_model=UserOut)
async def get_user_details(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    userRes = db.query(User).filter(User.user_id == user.user_id).all()
    if not userRes :
        raise HTTPException(status_code=404, detail="User not found")
    this_user = userRes[0]

    this_school = db.query(School).filter(School.school_id == this_user.school_id).first()

    return UserOut(
        id=this_user.user_id, 
        email=this_user.email,
        first_name=this_user.first_name,
        last_name=this_user.last_name,
        school_id=this_user.school_id,
        school_name=this_school.name,
        grade=this_user.grade,
        username=this_user.username
    )
