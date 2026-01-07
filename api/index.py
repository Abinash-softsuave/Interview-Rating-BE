"""
Vercel entrypoint for the FastAPI app.

Vercel detects this file as a Python Serverless Function and looks for
an ASGI-compatible `app` variable.
"""
import sys
import os
from pathlib import Path

# Add project root to Python path for Vercel serverless environment
# This ensures imports work correctly when the function is invoked
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now import after path is set
try:
    from app.controller.main_controller import create_app, setup_routes
    
    # Create FastAPI app
    app = create_app()
    setup_routes(app)
except Exception as e:
    # If app creation fails, create a minimal error handler app
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    
    app = FastAPI(title="AI Service - Error State")
    
    @app.get("/")
    async def error_root():
        return JSONResponse(
            status_code=500,
            content={
                "error": "FUNCTION_INVOCATION_FAILED",
                "message": f"Failed to initialize application: {str(e)}",
                "type": type(e).__name__
            }
        )
    
    @app.get("/health")
    async def error_health():
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": "Application initialization failed"
            }
        )


