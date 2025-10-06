"""
Manual test script for pension fund endpoints
"""
import uvicorn
import sys
import os

# Add the current directory to the path so we can import app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("Starting FastAPI application...")
    print("Access the API at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
