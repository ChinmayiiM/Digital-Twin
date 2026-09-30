"""Optional: fills SQLite with the synthetic demo user 'Alex'.

Run from the backend/ folder:   python seed_demo.py
Then open the dashboard by using the printed user id (or just use the onboarding screen instead).
"""
from datetime import datetime, timedelta

from app import models  # noqa: F401
from app.database import Base, SessionLocal, engine
from app.models import Goal, Preference, Task, User

Base.metadata.create_all(bind=engine)
db = SessionLocal()

user = User(name="Alex")
db.add(user)
db.flush()

exam_goal = Goal(user_id=user.id, title="Prepare for ML Exam", description="Complete exam preparation", priority="high")
assignment_goal = Goal(user_id=user.id, title="Complete ML Assignment", description="Finish the semester assignment", priority="high")
db.add_all([exam_goal, assignment_goal])
db.flush()

now = datetime.now().replace(hour=18, minute=0, second=0, microsecond=0)
db.add_all([
    Task(user_id=user.id, goal_id=assignment_goal.id, title="ML Assignment", description="Complete assignment",
         estimated_hours=5, deadline=now + timedelta(days=1), priority="high", status="pending"),
    Task(user_id=user.id, goal_id=exam_goal.id, title="ML Exam Preparation", description="Revise all units",
         estimated_hours=8, deadline=now + timedelta(days=3), priority="high", status="pending"),
])
db.add(Preference(user_id=user.id, available_hours_per_day=6, preferred_working_time="Morning"))
db.commit()
print(f"Demo user 'Alex' created with id {user.id}")
db.close()
