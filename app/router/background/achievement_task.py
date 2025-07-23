from app.model.points import Points
from app.model.user_badges import UserBadge
from app.model.badges import Badge
from app.model.achievements import *
from app.model.user_achievements import *
from app.model.attempts import *
from app.database.db import get_local_session
from app.database.session import SQLALCHEMY_DATABASE_URL
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

###################
### Achievement ###
###################

def check_achievement_and_award(user_id: str): 
    SessionLocal = get_local_session(SQLALCHEMY_DATABASE_URL)
    db = SessionLocal()
    try:
        # fetch achievement info
        # achievement_info = db.query(Achievement).all()
        # achievement_info_map = { 
        #     ach.id: {
        #         "name_en": ach.name_en, 
        #         "name_ind": ach.name_ind, 
        #         "description_en": ach.description_en, 
        #         "description_ind": ach.description_ind, 
        #         "points": ach.points
        #     } for ach in achievement_info 
        # }

        # fetch all user unlocked achievement 
        unlocked_achievement = db.query(UserAchievement.achievement_id).filter(UserAchievement.user_id == user_id).all()
        unlocked_set = set(u.achievement_id for u in unlocked_achievement)

        ############## DONE!
        ### ACH001 ### 
        ############## 
        # description: Finish any one quiz
        if 'ACH001' not in unlocked_set: 
            # Only get attempts for this user
            temp = db.query(Attempt).filter(Attempt.user_id == user_id).all()
            points = db.query(Points).filter(Points.user_id == user_id).first()
            if len(temp) > 0:  
                new_achievement = UserAchievement(
                    user_id=user_id,
                    achievement_id='ACH001', 
                    completed_at=datetime.now(), 
                    view_count=0
                )
                points.points += 10
                db.add(new_achievement)
                db.commit() 
                db.refresh(new_achievement)
                
        ############## DONE!
        ### ACH002 ###
        ##############
        # description: Complete any 10 quizzes total
        if 'ACH002' not in unlocked_set: 
            temp = db.query(Attempt).filter(Attempt.user_id == user_id).all()
            points = db.query(Points).filter(Points.user_id == user_id).first()
            if len(temp) >= 10: 
                new_achievement = UserAchievement(
                    user_id = user_id,
                    achievement_id = 'ACH002', 
                    completed_at = datetime.now(), 
                    view_count = 0
                )
                points.points += 50
                db.add(new_achievement)
                db.commit() 
                db.refresh(new_achievement)

        ##############
        ### ACH003 ###
        ##############
        # description: First time you score 5/5 on any single quiz
        if 'ACH003' not in unlocked_set: 
            temp = db.query(Attempt).filter(Attempt.user_id == user_id).all()
            points = db.query(Points).filter(Points.user_id == user_id).first()
            
            for atm in temp: 
                if(atm.fail_count == 0): 
                    new_achievement = UserAchievement(
                        user_id = user_id,
                        achievement_id = 'ACH003', 
                        completed_at = datetime.now(), 
                        view_count = 0
                    )
                    points.points += 15
                    db.add(new_achievement)
                    db.commit() 
                    db.refresh(new_achievement)
                    break

        ##############
        ### ACH004 ###
        ##############
        # description: Complete all quizzes for 5 weeks in a row (Attempt all 15 quizzes)
        if 'ACH004' not in unlocked_set: 
            pass

        ##############
        ### ACH005 ###
        ##############
        # description: Complete all quizzes for 10 weeks in a row (Attempt all 30 quizzes)
        if 'ACH005' not in unlocked_set: 
            pass

        ##############
        ### ACH006 ###
        ##############
        # description: Score 5/5 on any 5 different quizzes (non-consecutive or consecutive)
        if 'ACH006' not in unlocked_set: 
            temp = db.query(Attempt).filter(Attempt.user_id == user_id).all()
            points = db.query(Points).filter(Points.user_id == user_id).first()

            perfect_count = 0 

            for atm in temp: 
                if perfect_count == 5: 
                    new_achievement = UserAchievement(
                        user_id = user_id,
                        achievement_id = 'ACH006', 
                        completed_at = datetime.now(), 
                        view_count = 0
                    )
                    points.points += 20
                    db.add(new_achievement)
                    db.commit() 
                    db.refresh(new_achievement)
                    break
                if atm.fail_count == 0: 
                    perfect_count += 1

        ##############
        ### ACH007 ###
        ##############
        # description: Complete a redo on any single quiz (click on “Try Again” button)
        if 'ACH007' not in unlocked_set: 
            temp = db.query(Attempt).filter(Attempt.user_id == user_id).all()
            points = db.query(Points).filter(Points.user_id == user_id).first()
        for atm in temp: 
            if(atm.attempt_number == 2): 
                new_achievement = UserAchievement(
                        user_id = user_id,
                        achievement_id = 'ACH007', 
                        completed_at = datetime.now(), 
                        view_count = 0
                    )
                points.points += 5
                db.add(new_achievement)
                db.commit() 
                db.refresh(new_achievement)
                break
            
    finally: 
        db.close()
    pass