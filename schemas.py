"""
Pydantic models for request/response schemas
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


class BaseResponse(BaseModel):
    """Base response model"""
    success: bool = True
    message: str = "Success"
    timestamp: datetime = datetime.now()


class ErrorResponse(BaseResponse):
    """Error response model"""
    success: bool = False
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str = "healthy"
    service: str
    version: str = "1.0.0"
    timestamp: datetime = datetime.now()


# AI Service Models
class AIRequest(BaseModel):
    """Base AI request model"""
    input_data: Dict[str, Any]
    model_name: Optional[str] = "default"
    parameters: Optional[Dict[str, Any]] = None


class AIResponse(BaseResponse):
    """AI service response model"""
    result: Dict[str, Any]
    model_used: str
    processing_time: Optional[float] = None


# Video Analyzer Models
class VideoUrlRequest(BaseModel):
    """Video URL analysis request model"""
    video_url: str
    filename: Optional[str] = None  # Optional filename hint


class VideoAnalysisResponse(BaseModel):
    """Video analysis response model"""
    is_interview: bool
    summary: str
    key_questions: List[str]
    tone_and_professionalism: str
    rating: float  # Overall rating 0-10
    technical_strengths: List[str]
    technical_weaknesses: List[str]
    communication_rating: float  # 0-10
    technical_knowledge_rating: float  # 0-10
    follow_up_questions: List[str]
    interviewer_review: str  # Review of the interviewer's performance and conduct (how they conducted the interview)
    transcript: Optional[str] = None  # Full transcript if requested
    processing_time: Optional[float] = None


# User Service Models
class UserBase(BaseModel):
    """Base user model"""
    email: EmailStr
    username: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """User creation model"""
    password: str


class UserResponse(UserBase):
    """User response model"""
    id: int
    is_active: bool = True
    created_at: datetime

    class Config:
        from_attributes = True

