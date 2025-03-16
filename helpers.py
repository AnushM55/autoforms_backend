# Google Forms API setup
import os
import smtplib
from fastapi import HTTPException
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build 
from google.oauth2 import service_account

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
        
        # Set the correct answers for each question
        # This would require getting the question IDs after creating them
        # and then updating each question with the correct answer
        
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


quizzes_db = {}
forms_service = setup_google_forms_api()