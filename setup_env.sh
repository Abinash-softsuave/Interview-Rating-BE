#!/bin/bash

# Setup script for virtual environment and dependencies

echo "Setting up Python Microservice Architecture..."

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Create logs directory
echo "Creating logs directory..."
mkdir -p logs

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# Service Configuration
DEBUG=true
LOG_LEVEL=INFO

# Service URLs
API_GATEWAY_HOST=http://localhost:8000
AI_SERVICE_HOST=http://localhost:8001
USER_SERVICE_HOST=http://localhost:8002

# Security
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database (optional)
# DATABASE_URL=postgresql://user:password@localhost:5432/dbname
EOF
    echo ".env file created. Please update it with your configuration."
fi

echo "Setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source venv/bin/activate"
echo ""
echo "To run services manually:"
echo "  API Gateway: cd services/api-gateway && uvicorn main:app --reload --port 8000"
echo "  AI Service: cd services/ai-service && uvicorn main:app --reload --port 8001"
echo "  User Service: cd services/user-service && uvicorn main:app --reload --port 8002"
echo ""
echo "Or use Docker Compose:"
echo "  docker-compose up --build"

