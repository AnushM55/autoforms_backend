# schema.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from models import QuizStatus, Question, QuizCreate, QuizResponse, EmailRecipients

# Re-export all models to ensure they're included in the OpenAPI schema
__all__ = [
    "QuizStatus",
    "Question",
    "QuizCreate",
    "QuizResponse",
    "EmailRecipients",
    "OpenAPISchema",
    "QuizTextInput",
    "QuizListResponse",
    "ErrorResponse"
]

# Additional models for OpenAPI documentation
class QuizTextInput(BaseModel):
    """Input model for creating a quiz from text"""
    text: str = Field(..., description="The text content to parse into a quiz")
    suggested_title: Optional[str] = Field(None, description="Optional suggested title if none is found in the text")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "Quiz Title: Python Basics\n1. What is Python?\nA. A snake\nB. A programming language (correct)\nC. A game\nD. A database\n\n2. Which symbol is used for comments in Python?\nA. //\nB. /*\nC. # (correct)\nD. --",
                "suggested_title": "Python Programming Quiz"
            }
        }

class QuizListResponse(BaseModel):
    """Response model for listing quizzes"""
    quizzes: List[QuizResponse] = Field(..., description="List of quizzes")
    total: int = Field(..., description="Total number of quizzes")
    
    class Config:
        schema_extra = {
            "example": {
                "quizzes": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Python Basics",
                        "description": "Test your knowledge of Python",
                        "status": "draft",
                        "form_url": "https://docs.google.com/forms/d/example/edit",
                        "form_id": "example",
                        "created_at": "2023-01-01T12:00:00",
                        "updated_at": "2023-01-01T12:00:00"
                    }
                ],
                "total": 1
            }
        }

class ErrorResponse(BaseModel):
    """Error response model"""
    detail: str = Field(..., description="Error message")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": "Quiz not found"
            }
        }
        
class OpenAPISchema(BaseModel):
    """Model for the OpenAPI schema"""
    openapi: str
    info: Dict[str, Any]
    paths: Dict[str, Any]
    components: Dict[str, Any]