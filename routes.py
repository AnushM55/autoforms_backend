from models import *
from fastapi import FastAPI, HTTPException, Query, Body, Path, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from starlette.responses import HTMLResponse


from helpers import (
    create_google_form, 
    send_email_notification, 
    get_db, 
    get_quiz_by_id,
    get_all_quizzes,
    create_quiz_in_db,
    update_quiz_status,
    convert_db_quiz_to_response,
    get_google_form_details
)

from fastapi import APIRouter
router = APIRouter()

@router.get("/")
def sayHello():
    return "welcome to autoquiz backend"

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
@router.get("/quizdetails/{form_id}", response_model=List[Question])
async def get_form_details(form_id: str = Path(...)):
    """
    Get individual questions, options, and answers from a Google Form by its ID
    """
    try:
        questions = get_google_form_details(form_id)
        
        # Convert to Pydantic models
        pydantic_questions = []
        for q in questions:
            # Handle case where correct_answer_index is None (not a quiz or answer not available)
            if q["correct_answer_index"] is None:
                q["correct_answer_index"] = 0  # Default to first option
            
            pydantic_questions.append(Question(**q))
        
        return pydantic_questions
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add this to routes.py

from fastapi import UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from helpers import parse_quiz_with_gemini

class QuizTextInput(BaseModel):
    text: str
    suggested_title: Optional[str] = None

@router.post("/quizzes/from-file", response_model=QuizResponse, status_code=201)
async def create_quiz_from_file(
    file: UploadFile = File(...),
    suggested_title: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Create a new quiz by uploading a text file
    
    The file can be in any format - the Gemini API will extract quiz questions automatically.
    """
    if not file.filename.endswith(('.txt', '.md')):
        raise HTTPException(status_code=400, detail="Only text files (.txt, .md) are supported")
    
    # Read file content
    content = await file.read()
    file_content = content.decode('utf-8')
    
    # Parse quiz from content using Gemini
    quiz_data = await parse_quiz_with_gemini(file_content, suggested_title)
    
    # Create Google Form
    form_id, form_url = None, None
    try:
        form_id, form_url = create_google_form(quiz_data.title, quiz_data.description, quiz_data.questions)
    except Exception as e:
        # Log the error but continue (we'll store the quiz without form data)
        print(f"Error creating Google Form: {e}")
    
    # Store quiz in database
    db_quiz = create_quiz_in_db(db, quiz_data, form_id, form_url)
    
    # Convert to response model
    response_data = convert_db_quiz_to_response(db_quiz)
    return QuizResponse(**response_data)

@router.post("/quizzes/from-text", response_model=QuizResponse, status_code=200)
async def create_quiz_from_text(
    quiz_text: QuizTextInput,
    db: Session = Depends(get_db)
):
    """
    Create a quiz from text input
    
    The text can be structured or unstructured - the Gemini API will extract quiz questions automatically.
    """
    # Parse quiz from content using Gemini
    quiz_data = await parse_quiz_with_gemini(quiz_text.text, quiz_text.suggested_title)
    
    # Create Google Form
    form_id, form_url = None, None
    try:
        form_id, form_url = create_google_form(quiz_data.title, quiz_data.description, quiz_data.questions)
    except Exception as e:
        # Log the error but continue (we'll store the quiz without form data)
        print(f"Error creating Google Form: {e}")
    
    # Store quiz in database
    db_quiz = create_quiz_in_db(db, quiz_data, form_id, form_url)
    
    # Convert to response model
    response_data = convert_db_quiz_to_response(db_quiz)
    return QuizResponse(**response_data)
def custom_openapi(app):
    """
    Generate a custom OpenAPI schema with all model definitions properly exposed
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="AutoQuiz API",
        version="1.0.0",
        description="FastAPI based backend for AutoForms Quiz Management",
        routes=app.routes
    )
    
    # Add additional schema information if needed
    # openapi_schema["components"]["schemas"]["ExampleModel"] = {
    #     "type": "object",
    #     "properties": {
    #         "id": {"type": "string"},
    #         "name": {"type": "string"}
    #     }
    # }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def setup_openapi_routes(app: FastAPI):
    """
    Set up custom OpenAPI routes for better schema exposure
    """
    # Override the default OpenAPI schema
    app.openapi = lambda: custom_openapi(app)
    
    # Create a custom endpoint for OpenAPI JSON
    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_endpoint():
        return JSONResponse(custom_openapi(app))
    
    # Create a custom endpoint for Swagger UI
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=app.title + " - API Documentation",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css",
        )
    


def custom_openapi(app):
    """
    Generate a custom OpenAPI schema with all model definitions properly exposed
    """
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="AutoQuiz API",
        version="1.0.0",
        description="FastAPI based backend for AutoForms Quiz Management",
        routes=app.routes
    )
    
    # Add additional schema information if needed
    # openapi_schema["components"]["schemas"]["ExampleModel"] = {
    #     "type": "object",
    #     "properties": {
    #         "id": {"type": "string"},
    #         "name": {"type": "string"}
    #     }
    # }
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Add this to your main.py file

def setup_openapi_routes(app: FastAPI):
    """
    Set up custom OpenAPI routes for better schema exposure
    """
    # Override the default OpenAPI schema
    app.openapi = lambda: custom_openapi(app)
    
    # Create a custom endpoint for OpenAPI JSON
    @app.get("/openapi.json", include_in_schema=False)
    async def get_openapi_endpoint():
        return JSONResponse(custom_openapi(app))
    
    # Create a custom endpoint for Swagger UI
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url="/openapi.json",
            title=app.title + " - API Documentation",
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@4/swagger-ui.css",
        )
