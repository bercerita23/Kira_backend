from app.model.points import Points
from app.model.user_badges import UserBadge
from app.model.badges import Badge
from app.model.achievements import *
from app.model.user_achievements import *
from app.model.attempts import *
from app.database.db import get_async_db
from app.database.session import SQLALCHEMY_DATABASE_URL
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

###################
### Achievement ###
###################

async def check_achievement_and_award(user_id: str): 
    async with get_async_db() as db:
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
            result = await db.execute(
                select(UserAchievement.achievement_id).filter(UserAchievement.user_id == user_id)
            )
            unlocked_achievement = result.all()
            unlocked_set = set(u[0] for u in unlocked_achievement)

            ############## DONE!
            ### ACH001 ### 
            ############## 
            # description: Finish any one quiz
            if 'ACH001' not in unlocked_set: 
                # Only get attempts for this user
                attempts_result = await db.execute(
                    select(Attempt).filter(Attempt.user_id == user_id)
                )
                temp = attempts_result.scalars().all()
                
                points_result = await db.execute(
                    select(Points).filter(Points.user_id == user_id)
                )
                points = points_result.scalar_one_or_none()
                if len(temp) > 0:  
                    new_achievement = UserAchievement(
                        user_id=user_id,
                        achievement_id='ACH001', 
                        completed_at=datetime.now(), 
                        view_count=0
                    )
                    points.points += 10
                    db.add(new_achievement)
                    await db.commit() 
                    db.refresh(new_achievement)
                    
            ############## DONE!
            ### ACH002 ###
            ##############
            # description: Complete any 10 quizzes total
            if 'ACH002' not in unlocked_set: 
                attempts_result = await db.execute(
                    select(Attempt).filter(Attempt.user_id == user_id)
                )
                temp = attempts_result.scalars().all()
                
                points_result = await db.execute(
                    select(Points).filter(Points.user_id == user_id)
                )
                points = points_result.scalar_one_or_none()
                if len(temp) >= 10: 
                    new_achievement = UserAchievement(
                        user_id = user_id,
                        achievement_id = 'ACH002', 
                        completed_at = datetime.now(), 
                        view_count = 0
                    )
                    points.points += 50
                    db.add(new_achievement)
                    await db.commit() 
                    db.refresh(new_achievement)

            ##############
            ### ACH003 ###
            ##############
            # description: First time you score 5/5 on any single quiz
            if 'ACH003' not in unlocked_set: 
                attempts_result = await db.execute(
                    select(Attempt).filter(Attempt.user_id == user_id)
                )
                temp = attempts_result.scalars().all()
                
                points_result = await db.execute(
                    select(Points).filter(Points.user_id == user_id)
                )
                points = points_result.scalar_one_or_none()
                
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
                        await db.commit() 
                        db.refresh(new_achievement)
                        break

            ##############
            ### ACH004 ###
            ##############
            # description: Complete all quizzes for 5 weeks in a row (Attempt all 15 quizzes)
            if 'ACH004' not in unlocked_set: 
                attempts_result = await db.execute(
                    select(Attempt).filter(Attempt.user_id == user_id)
                )
                temp = attempts_result.scalars().all() # all the attempt of this user
                # brainstorm: if the quiz id is consecutive thorugh out the attempts, the user is guicci
                # reduce the problem to two weeks: only need 6 consecutive quiz id now 
                # user attemp: 1 2 3   5 6 7 8 9 10     12 13 14
                s = set(t.quiz_id for t in temp)
                longest = 0

                for n in s:
                    if n - 1 not in s: # find the first num 
                        length = 1

                        while n + length in s:
                            length += 1
                        
                        longest = max(longest, length)
                
                if longest >= 15: # give ACH004
                    new_achievement = UserAchievement(
                            user_id = user_id,
                            achievement_id = 'ACH004', 
                            completed_at = datetime.now(), 
                            view_count = 0
                        )
                    points.points += 50
                    db.add(new_achievement)
                    await db.commit() 
                    db.refresh(new_achievement)



            ##############
            ### ACH005 ###
            ##############
            # description: Complete all quizzes for 10 weeks in a row (Attempt all 30 quizzes)
            if 'ACH005' not in unlocked_set: 
                s = set(t.quiz_id for t in temp)
                longest = 0

                for n in s:
                    if n - 1 not in s: # find the first num 
                        length = 1

                        while n + length in s:
                            length += 1
                        
                        longest = max(longest, length)
                
                if longest >= 30: # give ACH005
                    new_achievement = UserAchievement(
                            user_id = user_id,
                            achievement_id = 'ACH005', 
                            completed_at = datetime.now(), 
                            view_count = 0
                        )
                    points.points += 50
                    db.add(new_achievement)
                    await db.commit() 
                    db.refresh(new_achievement)

            ##############
            ### ACH006 ###
            ##############
            # description: Score 5/5 on any 5 different quizzes (non-consecutive or consecutive)
            if 'ACH006' not in unlocked_set: 
                attempts_result = await db.execute(
                    select(Attempt).filter(Attempt.user_id == user_id)
                )
                temp = attempts_result.scalars().all()
                
                points_result = await db.execute(
                    select(Points).filter(Points.user_id == user_id)
                )
                points = points_result.scalar_one_or_none()

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
                        await db.commit() 
                        db.refresh(new_achievement)
                        break
                    if atm.fail_count == 0: 
                        perfect_count += 1

            ##############
            ### ACH007 ###
            ##############
            # description: Complete a redo on any single quiz (click on “Try Again” button)
            if 'ACH007' not in unlocked_set: 
                attempts_result = await db.execute(
                    select(Attempt).filter(Attempt.user_id == user_id)
                )
                temp = attempts_result.scalars().all()
                
                points_result = await db.execute(
                    select(Points).filter(Points.user_id == user_id)
                )
                points = points_result.scalar_one_or_none()
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
                        await db.commit() 
                        db.refresh(new_achievement)
                        break

        except Exception as e:
            # Log the error but don't re-raise to prevent breaking the background task
            print(f"Error checking achievements for user {user_id}: {e}")