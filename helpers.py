# Google Forms API setup
import os
import json
import json_repair
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
import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google import genai
import os
import json
from fastapi import HTTPException
from models import QuizCreate, Question

# If modifying these SCOPES, delete the token.json file and re-authenticate

def get_gmail_service():
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
    """Authenticate and return a Gmail API service instance."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

def send_email_notification(recipients, quiz_title, form_url):
    """Send email notification with quiz link using Gmail API."""
    try:
        service = get_gmail_service()
        sender_email = "your-email@gmail.com"  # Replace with your verified email

        # Create email message
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = f"Quiz Invitation: {quiz_title}"

        body = f"""
        Hello,

        You have been invited to take the quiz "{quiz_title}".

        Access the quiz here: {form_url}

        Thank you!
        """

        msg.attach(MIMEText(body, "plain"))

        # Encode message in base64
        raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        message = {"raw": raw_message}

        # Send email using Gmail API
        service.users().messages().send(userId="me", body=message).execute()

        print("Email sent successfully!")
        return True

    except Exception as e:
        print(f"Error sending email: {e}")
        return False


def setup_google_forms_api():
    try:
        SCOPES = ['https://www.googleapis.com/auth/forms.body','https://www.googleapis.com/auth/forms.body.readonly']
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
                                'questionId' : f'{idx}',
                                'required': True,
                            "grading": {
                                "pointValue": 1,
                                "correctAnswers": {
                                    "answers":[{
                                        "value": question.options[question.correct_answer_index]
                                    }]
                                },
                                "whenRight": {
                                    "text": "Correct"
                                },
                                "whenWrong": {
                                    "text": "Incorrect"
                                }
                            },
                                'choiceQuestion': {
                                    'type': 'RADIO',
                                    'options': [{'value': option} for option in question.options],
                                    'shuffle': True
                                },

                            },
                        }
                    },
                    'location': {
                        'index': idx
                    }
                }
            }
            question_requests.append(item_request)
        
        # Execute batch update to add questions
        
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
        
        if question_requests:
            forms_service.forms().batchUpdate(
                formId=form_id,
                body={'requests': question_requests}
            ).execute()
        return form_id, form_url
    except Exception as e:
        print(f"Error creating Google Form: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create Google Form: {str(e)}")


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

def get_google_form_details(form_id):
    """Retrieve questions, options, and answers from a Google Form by its ID"""
    if not forms_service:
        raise HTTPException(status_code=500, detail="Google Forms API not available")
    
    try:
        # Get the form
        form = forms_service.forms().get(formId=form_id).execute()
        
        # Extract questions, options, and answers
        questions = []
        
        if 'items' in form:
            for item in form['items']:
                if 'questionItem' in item:
                    question_data = item['questionItem']['question']
                    question_text = item['title']
                    
                    # Handle different question types
                    if 'choiceQuestion' in question_data:
                        options = []
                        for option in question_data['choiceQuestion']['options']:
                            options.append(option['value'])
                        
                        # For quizzes, answers may be available
                        correct_answer_index = None
                        if 'grading' in question_data:
                            if 'correctAnswers' in question_data['grading']:
                                correct_answers = question_data['grading']['correctAnswers']
                                # Find index of correct answer in options
                                for i, option in enumerate(options):
                                    if option in correct_answers:
                                        correct_answer_index = i
                                        break
                        
                        questions.append({
                            "text": question_text,
                            "options": options,
                            "correct_answer_index": correct_answer_index
                        })
        
        return questions
    except Exception as e:
        print(f"Error retrieving Google Form: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve Google Form: {str(e)}")


# Add this to helpers.py

gemini_api_key = os.getenv("GEMINI_API_KEY")

async def parse_quiz_with_gemini(content: str, suggested_title: str = None) -> QuizCreate:
    """
    Use Google's Gemini API to parse any text input and extract a quiz structure
    
    Parameters:
    - content: The text content to parse (can be structured or unstructured)
    - suggested_title: Optional title suggestion if none is found in the content
    
    Returns a QuizCreate object or raises an HTTPException if parsing fails
    """
    if not gemini_api_key:
        raise HTTPException(status_code=500, detail="Gemini API key not configured")
    
    try:
        title_hint = None
        if suggested_title:
            title_hint = f"Use '{suggested_title}' as the quiz title if no title is clearly indicated in the text."

        
        # Create the prompt
        prompt = f"""
        Extract a quiz from the following text. {title_hint}
        
        Return a JSON object with this exact structure:
        {{
            "title": "Quiz title",
            "description": "Brief description of the quiz",
            "questions": [
                {{
                    "text": "Question text",
                    "options": ["Option A", "Option B", "Option C", "Option D"],
                    "correct_answer_index": (index)// index of correct answer
                    "grading":{{
                            "pointValue":1,
                            "correctAnswers":{{
                                "answers":{{
                                    "value": "(value)" // value of the correct option
                                }}    
                            }},
                            "whenRight":{{
                                "text":"Correct"
                            
                            }},
                            "whenWrong:":{{
                                "text":"Incorrect"
                            }}
                    }}
                }},
                // more questions...
            ]
        }}
        
        Make sure:
        1. Each question has exactly one correct answer
        2. The correct_answer_index is 0-based (0=first option, 1=second option, etc.)
        3. Include between 2-4 options per question
        4. If the text doesn't clearly specify which answer is correct, make your best guess
        5. Only include the JSON output, nothing else
        
        Text to extract quiz from:
        {content}
        """
        

        client = genai.Client(api_key = gemini_api_key)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )

        # Use the response as a JSON string.
        print(response.text)

        # Make the API request
            
        if response == None:
            raise HTTPException(status_code=500, detail=f"Error from Gemini API: {response.text}")
            
        quiz_data = json_repair.loads(response.text)
            
        # Extract the JSON from the response
        
        # Clean up the JSON text to handle possible markdown formatting
        
        
        # Convert to QuizCreate model
        questions = []
        for q in quiz_data["questions"]:
            questions.append(Question(
                text=q["text"],
                options=q["options"],
                correct_answer_index=q["correct_answer_index"]
                ))
            
        return QuizCreate(
                title=quiz_data["title"],
                description=quiz_data.get("description", ""),
                questions=questions
            )
            
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse quiz format: {str(e)}")
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required field in quiz data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing quiz with Gemini API: {str(e)}")
