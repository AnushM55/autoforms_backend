# models.py - Updated version with SQLAlchemy models

from pydantic import BaseModel
from typing import Optional, List
from pydantic import Field
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLAEnum, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# SQLAlchemy setup
DATABASE_URL = "sqlite:///./autoforms.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Pydantic models
class QuizStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    DELETED = "deleted"

class Question(BaseModel):
    text: str
    options: List[str]
    correct_answer_index: int

class QuizCreate(BaseModel):
    title: str
    description: Optional[str] = None
    questions: List[Question]

class QuizResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: QuizStatus
    form_url: Optional[str] = None
    form_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

class EmailRecipients(BaseModel):
    recipients: List[str] = Field(..., description="List of email addresses to send the quiz to")

# SQLAlchemy models
class QuizDB(Base):
    __tablename__ = "quizzes"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(SQLAEnum(QuizStatus), default=QuizStatus.DRAFT)
    form_url = Column(String, nullable=True)
    form_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    questions = relationship("QuestionDB", back_populates="quiz", cascade="all, delete-orphan")

class QuestionDB(Base):
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(String, ForeignKey("quizzes.id"))
    text = Column(String, nullable=False)
    options = Column(String, nullable=False)  # Stored as JSON string
    correct_answer_index = Column(Integer, nullable=False)
    
    quiz = relationship("QuizDB", back_populates="questions")

# Create tables
Base.metadata.create_all(bind=engine)

# Helper function to get db session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()