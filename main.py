"""
Main application entry point
"""
from app.controller.main_controller import create_app, setup_routes
from app.db.database import get_settings
import uvicorn

# Create FastAPI app
app = create_app()

# Setup routes
setup_routes(app)

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=settings.DEBUG)

