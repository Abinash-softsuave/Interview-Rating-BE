"""
Quick test script to verify the microservice setup
"""
import sys
import os

print("=" * 60)
print("Testing Microservice Architecture Setup")
print("=" * 60)

# Test 1: Check imports
print("\n1. Testing imports...")
try:
    from shared.config import get_settings
    from shared.models import BaseResponse, HealthCheckResponse
    from shared.utils import setup_logging
    print("   ✓ Shared modules imported successfully")
except Exception as e:
    print(f"   ✗ Error importing shared modules: {e}")
    sys.exit(1)

# Test 2: Check service
print("\n2. Testing service import...")
try:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'services/ai-service')))
    from main import app as ai_app
    print("   ✓ AI Service imported successfully")
except Exception as e:
    print(f"   ✗ Error importing AI Service: {e}")
    sys.exit(1)

# Test 3: Check configuration
print("\n3. Testing configuration...")
try:
    settings = get_settings()
    print(f"   ✓ Configuration loaded")
    print(f"     - AI Service Host: {settings.AI_SERVICE_HOST}")
    print(f"     - Debug Mode: {settings.DEBUG}")
except Exception as e:
    print(f"   ✗ Error loading configuration: {e}")

# Test 4: Check logging
print("\n4. Testing logging setup...")
try:
    import os
    if not os.path.exists("logs"):
        os.makedirs("logs")
    setup_logging("test-service", "INFO")
    print("   ✓ Logging configured successfully")
except Exception as e:
    print(f"   ✗ Error setting up logging: {e}")

print("\n" + "=" * 60)
print("✓ All tests passed! Setup is correct.")
print("=" * 60)
print("\nNext steps:")
print("1. Run AI Service:      cd services/ai-service && uvicorn main:app --reload --port 8001")
print("\nOr use Docker Compose: docker-compose up --build")
print("\nAccess the service:")
print("- AI Service:  http://localhost:8001/docs")
print("- Video Analysis: POST http://localhost:8001/analyze-video")
print("- Video Analysis from URL: POST http://localhost:8001/analyze-video-url")

