# Google Forms API setup
import os
import json
import smtplib
from fastapi import HTTPException, Depends
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build 
from google.oauth2 import service_account
from sqlalchemy.orm import Session
from models import QuizDB, QuestionDB, get_db, QuizStatus, Question
from typing import List
import uuid
from datetime import datetime

def setup_google_forms_api():
    try:
        SCOPES = ['https://www.googleapis.com/auth/forms.body']
        creds_file = os.environ.get('GOOGLE_CREDENTIALS_FILE', 'credentials2.json')
        
        # Check if credentials file exists
        if not os.path.exists(creds_file):
            print(f"Warning: Google credentials file {creds_file} not found.")
            return None
            
        credentials = service_account.Credentials.from_service_account_file(
            creds_file, scopes=SCOPES)
        forms_service = build('forms', 'v1', credentials=credentials)
        return forms_service
    except Exception as e:
        print(f"Error setting up Google Forms API: {e}")
        return None

# Initialize Google Forms service
forms_service = setup_google_forms_api()

# Helper functions
def create_google_form(title, description, questions):
    """Create a Google Form using the Google Forms API"""
    if not forms_service:
        raise HTTPException(status_code=500, detail="Google Forms API not available")
    
    try:
        # Create a new form
        form_body = {
            'info': {
                'title': title,
            }
        }
        
        created_form = forms_service.forms().create(body=form_body).execute()
        form_id = created_form['formId']
        form_url = f"https://docs.google.com/forms/d/{form_id}/edit"
        
        # Add questions to the form
        question_requests = []
        for idx, question in enumerate(questions):
            item_request = {
                'createItem': {
                    'item': {
                        'title': question.text,
                        'questionItem': {
                            'question': {
                                'required': True,
                                'choiceQuestion': {
                                    'type': 'RADIO',
                                    'options': [{'value': option} for option in question.options],
                                    'shuffle': False
                                }
                            }
                        }
                    },
                    'location': {
                        'index': idx
                    }
                }
            }
            question_requests.append(item_request)
        
        # Execute batch update to add questions
        if question_requests:
            forms_service.forms().batchUpdate(
                formId=form_id,
                body={'requests': question_requests}
            ).execute()
        
        # Set the form to be a quiz
        quiz_settings_request = {
            'updateSettings': {
                'settings': {
                    'quizSettings': {
                        'isQuiz': True
                    }
                },
                'updateMask': 'quizSettings.isQuiz'
            }
        }
        
        forms_service.forms().batchUpdate(
            formId=form_id,
            body={'requests': [quiz_settings_request]}
        ).execute()
        
        return form_id, form_url
    except Exception as e:
        print(f"Error creating Google Form: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create Google Form: {str(e)}")

def send_email_notification(recipients, quiz_title, form_url):
    """Send email notification with quiz link to recipients"""
    try:
        # Email configuration (replace with actual SMTP settings)
        smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
        smtp_port = int(os.environ.get("SMTP_PORT", 587))
        smtp_username = os.environ.get("SMTP_USERNAME", "your-email@gmail.com")
        smtp_password = os.environ.get("SMTP_PASSWORD", "your-password")
        sender_email = os.environ.get("SENDER_EMAIL", smtp_username)
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = f"Quiz Invitation: {quiz_title}"
        
        body = f"""
        Hello,
        
        You have been invited to take the quiz "{quiz_title}".
        
        Access the quiz here: {form_url}
        
        Thank you!
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Database operations
def get_quiz_by_id(db: Session, quiz_id: str):
    """Get a quiz by ID"""
    return db.query(QuizDB).filter(QuizDB.id == quiz_id).first()

def get_all_quizzes(db: Session, status=None):
    """Get all quizzes, optionally filtered by status"""
    query = db.query(QuizDB).filter(QuizDB.status != QuizStatus.DELETED)
    if status:
        query = query.filter(QuizDB.status == status)
    return query.all()

def create_quiz_in_db(db: Session, quiz_data, form_id=None, form_url=None):
    """Create a new quiz in the database"""
    quiz_id = str(uuid.uuid4())
    current_time = datetime.now()
    
    db_quiz = QuizDB(
        id=quiz_id,
        title=quiz_data.title,
        description=quiz_data.description,
        status=QuizStatus.DRAFT,
        form_id=form_id,
        form_url=form_url,
        created_at=current_time,
        updated_at=current_time
    )
    
    db.add(db_quiz)
    db.commit()
    
    # Add questions
    for question in quiz_data.questions:
        db_question = QuestionDB(
            quiz_id=quiz_id,
            text=question.text,
            options=json.dumps(question.options),
            correct_answer_index=question.correct_answer_index
        )
        db.add(db_question)
    
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

def update_quiz_status(db: Session, quiz_id: str, new_status: QuizStatus):
    """Update the status of a quiz"""
    db_quiz = get_quiz_by_id(db, quiz_id)
    if not db_quiz:
        return None
    
    db_quiz.status = new_status
    db_quiz.updated_at = datetime.now()
    db.commit()
    db.refresh(db_quiz)
    return db_quiz

def convert_db_quiz_to_response(db_quiz):
    """Convert a DB quiz model to a response model"""
    # Get questions
    questions = []
    for q in db_quiz.questions:
        questions.append({
            "text": q.text,
            "options": json.loads(q.options),
            "correct_answer_index": q.correct_answer_index
        })
    
    return {
        "id": db_quiz.id,
        "title": db_quiz.title,
        "description": db_quiz.description,
        "status": db_quiz.status,
        "form_url": db_quiz.form_url,
        "form_id": db_quiz.form_id,
        "created_at": db_quiz.created_at,
        "updated_at": db_quiz.updated_at,
        "questions": questions
    }