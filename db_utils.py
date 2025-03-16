# db_utils.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, QuizDB, QuestionDB, QuizStatus
import json
from datetime import datetime
import uuid

def init_db(db_path="./autoforms.db"):
    """Initialize the database and return a session"""
    # Remove existing database if needed
    if os.path.exists(db_path) and db_path != ":memory:":
        os.remove(db_path)
    
    # Create database
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    
    # Create session
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

def seed_sample_data(db):
    """Seed the database with sample quizzes"""
    # Sample Quiz 1
    quiz1_id = str(uuid.uuid4())
    quiz1 = QuizDB(
        id=quiz1_id,
        title="Python Basics Quiz",
        description="Test your knowledge of Python fundamentals",
        status=QuizStatus.DRAFT,
        form_id="sample1",
        form_url="https://docs.google.com/forms/d/sample1/edit",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(quiz1)
    
    # Questions for Quiz 1
    q1 = QuestionDB(
        quiz_id=quiz1_id,
        text="What is Python?",
        options=json.dumps([
            "A programming language", 
            "A snake", 
            "A game", 
            "An operating system"
        ]),
        correct_answer_index=0
    )
    
    q2 = QuestionDB(
        quiz_id=quiz1_id,
        text="Which symbol is used for comments in Python?",
        options=json.dumps([
            "//", 
            "/*", 
            "#", 
            "--"
        ]),
        correct_answer_index=2
    )
    
    db.add(q1)
    db.add(q2)
    
    # Sample Quiz 2
    quiz2_id = str(uuid.uuid4())
    quiz2 = QuizDB(
        id=quiz2_id,
        title="JavaScript Fundamentals",
        description="Test your knowledge of JavaScript",
        status=QuizStatus.APPROVED,
        form_id="sample2",
        form_url="https://docs.google.com/forms/d/sample2/edit",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    
    db.add(quiz2)
    
    # Questions for Quiz 2
    q3 = QuestionDB(
        quiz_id=quiz2_id,
        text="What is JavaScript primarily used for?",
        options=json.dumps([
            "Server-side programming", 
            "Web development", 
            "Mobile app development", 
            "Database management"
        ]),
        correct_answer_index=1
    )
    
    q4 = QuestionDB(
        quiz_id=quiz2_id,
        text="Which keyword is used to declare variables in JavaScript?",
        options=json.dumps([
            "dim", 
            "var", 
            "variable", 
            "declare"
        ]),
        correct_answer_index=1
    )
    
    db.add(q3)
    db.add(q4)
    
    # Commit changes
    db.commit()
    
    return [quiz1_id, quiz2_id]

if __name__ == "__main__":
    # If run directly, initialize and seed the database
    db = init_db()
    seed_sample_data(db)
    print("Database initialized and seeded with sample data.")