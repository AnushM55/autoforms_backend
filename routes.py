from models import *
from fastapi import HTTPException, Query, Body, Path
from typing import List, Optional
import uuid
from datetime import datetime
from helpers import create_google_form, send_email_notification , quizzes_db

from fastapi import APIRouter
router = APIRouter(
)

# Routes
@router.post("/quizzes/", response_model=QuizResponse, status_code=201)
async def create_quiz(quiz: QuizCreate = Body(...)):
    """
    Create a new quiz in draft status
    """
    # Generate a unique ID for the quiz
    quiz_id = str(uuid.uuid4())
    current_time = datetime.now()
    
    # Create Google Form
    form_id, form_url = None, None
    try:
        form_id, form_url = create_google_form(quiz.title, quiz.description, quiz.questions)
    except Exception as e:
        # Log the error but continue (we'll store the quiz without form data)
        print(f"Error creating Google Form: {e}")
    
    # Store quiz in database
    quiz_data = {
        "id": quiz_id,
        "title": quiz.title,
        "description": quiz.description,
        "status": QuizStatus.DRAFT,
        "form_id": form_id,
        "form_url": form_url,
        "questions": [q.dict() for q in quiz.questions],
        "created_at": current_time,
        "updated_at": current_time
    }
    
    quizzes_db[quiz_id] = quiz_data
    
    return QuizResponse(**quiz_data)

@router.get("/quizzes/", response_model=List[QuizResponse])
async def get_quizzes(status: Optional[QuizStatus] = Query(None)):
    """
    Get all quizzes, optionally filtered by status
    """
    if status:
        filtered_quizzes = [q for q in quizzes_db.values() if q["status"] == status and q["status"] != QuizStatus.DELETED]
    else:
        filtered_quizzes = [q for q in quizzes_db.values() if q["status"] != QuizStatus.DELETED]
    
    return filtered_quizzes

@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: str = Path(...)):
    """
    Get details for a specific quiz
    """
    if quiz_id not in quizzes_db:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    quiz = quizzes_db[quiz_id]
    if quiz["status"] == QuizStatus.DELETED:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    return quiz

@router.post("/quizzes/{quiz_id}/routerrove", response_model=QuizResponse)
async def routerrove_quiz(
    quiz_id: str = Path(...),
    email_data: EmailRecipients = Body(...)
):
    """
    routerrove a quiz and send email notifications
    """
    if quiz_id not in quizzes_db:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    quiz = quizzes_db[quiz_id]
    
    # Check if the quiz is in draft status
    if quiz["status"] != QuizStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft quizzes can be routerroved")
    
    # Send email notification
    if not quiz["form_url"]:
        raise HTTPException(status_code=400, detail="Quiz does not have a valid Google Form URL")
    
    email_sent = send_email_notification(
        email_data.recipients,
        quiz["title"],
        quiz["form_url"]
    )
    
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send email notifications")
    
    # Update quiz status
    quiz["status"] = QuizStatus.routerROVED
    quiz["updated_at"] = datetime.now()
    quizzes_db[quiz_id] = quiz
    
    return quiz

@router.delete("/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(quiz_id: str = Path(...)):
    """
    Mark a quiz as deleted
    """
    if quiz_id not in quizzes_db:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    quiz = quizzes_db[quiz_id]
    quiz["status"] = QuizStatus.DELETED
    quiz["updated_at"] = datetime.now()
    quizzes_db[quiz_id] = quiz
    
    return None

# Root endpoint
@router.get("/")
async def root():
    return {"message": "Google Forms Quiz System API is running"}
