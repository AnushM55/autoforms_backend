    
from pydantic import BaseModel
from typing import Optional, List
from pydantic import Field
from enum import Enum
from datetime import datetime
# Models
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