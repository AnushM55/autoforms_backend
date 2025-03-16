from models import *
from fastapi import HTTPException, Query, Body, Path, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from helpers import (
    create_google_form, 
    send_email_notification, 
    get_db, 
    get_quiz_by_id,
    get_all_quizzes,
    create_quiz_in_db,
    update_quiz_status,
    convert_db_quiz_to_response
)

from fastapi import APIRouter
router = APIRouter()

# Routes
@router.post("/quizzes/", response_model=QuizResponse, status_code=201)
async def create_quiz(quiz: QuizCreate = Body(...), db: Session = Depends(get_db)):
    """
    Create a new quiz in draft status
    """
    # Create Google Form
    form_id, form_url = None, None
    try:
        form_id, form_url = create_google_form(quiz.title, quiz.description, quiz.questions)
    except Exception as e:
        # Log the error but continue (we'll store the quiz without form data)
        print(f"Error creating Google Form: {e}")
    
    # Store quiz in database
    db_quiz = create_quiz_in_db(db, quiz, form_id, form_url)
    
    # Convert to response model
    response_data = convert_db_quiz_to_response(db_quiz)
    return QuizResponse(**response_data)

@router.get("/quizzes/", response_model=List[QuizResponse])
async def get_quizzes(status: Optional[QuizStatus] = Query(None), db: Session = Depends(get_db)):
    """
    Get all quizzes, optionally filtered by status
    """
    quizzes = get_all_quizzes(db, status)
    return [QuizResponse(**convert_db_quiz_to_response(quiz)) for quiz in quizzes]

# This is a snippet to fix the approve_quiz route that was incorrectly named in the original code
# The rest of the routes.py implementation remains the same as in the previous artifact

@router.post("/quizzes/{quiz_id}/approve", response_model=QuizResponse)
async def approve_quiz(
    quiz_id: str = Path(...),
    email_data: EmailRecipients = Body(...),
    db: Session = Depends(get_db)
):
    """
    Approve a quiz and send email notifications
    """
    quiz = get_quiz_by_id(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    # Check if the quiz is in draft status
    if quiz.status != QuizStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Only draft quizzes can be approved")
    
    # Send email notification
    if not quiz.form_url:
        raise HTTPException(status_code=400, detail="Quiz does not have a valid Google Form URL")
    
    email_sent = send_email_notification(
        email_data.recipients,
        quiz.title,
        quiz.form_url
    )
    
    if not email_sent:
        raise HTTPException(status_code=500, detail="Failed to send email notifications")
    
    # Update quiz status
    updated_quiz = update_quiz_status(db, quiz_id, QuizStatus.APPROVED)
    
    return QuizResponse(**convert_db_quiz_to_response(updated_quiz))

@router.get("/quizzes/{quiz_id}", response_model=QuizResponse)
async def get_quiz(quiz_id: str = Path(...), db: Session = Depends(get_db)):
    """
    Get details for a specific quiz
    """
    quiz = get_quiz_by_id(db, quiz_id)
    if not quiz or quiz.status == QuizStatus.DELETED:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    return QuizResponse(**convert_db_quiz_to_response(quiz))


@router.delete("/quizzes/{quiz_id}", status_code=204)
async def delete_quiz(quiz_id: str = Path(...), db: Session = Depends(get_db)):
    """
    Mark a quiz as deleted
    """
    quiz = get_quiz_by_id(db, quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    
    updated_quiz = update_quiz_status(db, quiz_id, QuizStatus.DELETED)

    return QuizResponse(**convert_db_quiz_to_response(updated_quiz))