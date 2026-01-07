"""
Database configuration and utilities
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional


# Find project root (where .env file is located)
def find_project_root():
    """Find the project root directory by looking for .env file"""
    current_dir = Path(__file__).resolve()
    # Go up from app/db/database.py -> app -> db -> project root
    project_root = current_dir.parent.parent.parent
    
    # Verify .env exists in project root
    env_file = project_root / ".env"
    if env_file.exists():
        return str(project_root)
    
    # Fallback: try current working directory
    cwd = Path.cwd()
    if (cwd / ".env").exists():
        return str(cwd)
    
    # Last resort: return project root anyway
    return str(project_root)


class Settings(BaseSettings):
    """Application settings"""
    
    # Service settings
    SERVICE_NAME: str = "ai-service"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # API Gateway
    API_GATEWAY_HOST: str = "http://localhost:8000"
    
    # AI Service
    AI_SERVICE_HOST: str = "http://localhost:8001"
    
    # User Service
    USER_SERVICE_HOST: str = "http://localhost:8002"
    
    # Database
    DATABASE_URL: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # AI Service - Video Analyzer
    GEMINI_API_KEY: Optional[str] = None  # Set in .env file
    WHISPER_MODEL: str = "base"  # Options: tiny, base, small, medium, large
    MAX_VIDEO_SIZE_MB: int = 5000  # Maximum video file size in MB
    
    # Alternative transcription (preferred for serverless)
    USE_ALTERNATIVE_TRANSCRIPTION: bool = True  # Enable API-based transcription
    TRANSCRIPTION_API_KEY: Optional[str] = None  # API key for alternative service
    TRANSCRIPTION_SERVICE: str = "assemblyai"  # Options: whisper, google, azure, assemblyai
    
    class Config:
        env_file = os.path.join(find_project_root(), ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


def get_settings() -> Settings:
    """Get settings instance""" 
    return Settings()



