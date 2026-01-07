"""
Vercel entrypoint for the FastAPI app.

Vercel detects this file as a Python Serverless Function and looks for
an ASGI-compatible `app` variable.
"""

from app.controller.main_controller import create_app, setup_routes

# Create FastAPI app
app = create_app()
setup_routes(app)


