@echo off
REM Setup script for virtual environment and dependencies (Windows)

echo Setting up Python Microservice Architecture...

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Create logs directory
echo Creating logs directory...
if not exist logs mkdir logs

REM Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file...
    (
        echo # Service Configuration
        echo DEBUG=true
        echo LOG_LEVEL=INFO
        echo.
        echo # Service URLs
        echo API_GATEWAY_HOST=http://localhost:8000
        echo AI_SERVICE_HOST=http://localhost:8001
        echo USER_SERVICE_HOST=http://localhost:8002
        echo.
        echo # Security
        echo SECRET_KEY=your-secret-key-change-in-production
        echo ALGORITHM=HS256
        echo ACCESS_TOKEN_EXPIRE_MINUTES=30
        echo.
        echo # Database (optional)
        echo # DATABASE_URL=postgresql://user:password@localhost:5432/dbname
    ) > .env
    echo .env file created. Please update it with your configuration.
)

echo.
echo Setup complete!
echo.
echo To activate the virtual environment, run:
echo   venv\Scripts\activate
echo.
echo To run services manually:
echo   API Gateway: cd services\api-gateway ^&^& uvicorn main:app --reload --port 8000
echo   AI Service: cd services\ai-service ^&^& uvicorn main:app --reload --port 8001
echo   User Service: cd services\user-service ^&^& uvicorn main:app --reload --port 8002
echo.
echo Or use Docker Compose:
echo   docker-compose up --build

