"""
Clean FastAPI application startup without SQLAlchemy conflicts
"""
import os
import sys
from pathlib import Path

# Set environment for clean database
os.environ["DATABASE_URL"] = "sqlite:///./clean_retire.db"

# Clear any existing mappers before any imports
from sqlalchemy.orm import clear_mappers
clear_mappers()

# Import FastAPI and basic components
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Create clean FastAPI app
app = FastAPI(
    title="Retirement Planning System - Clean",
    description="Clean API for retirement planning system",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "Clean Retirement Planning System API", "status": "running"}

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "database": "clean"}

@app.get("/api/v1/health")
def health_check_v1():
    """Health check endpoint with API prefix"""
    return {"status": "ok", "version": "1.0.0"}

# Basic client endpoints without SQLAlchemy
@app.get("/api/v1/clients")
def list_clients():
    """List all clients - mock implementation"""
    return {
        "clients": [
            {"id": 1, "name": "Test Client 1", "id_number": "123456789"},
            {"id": 2, "name": "Test Client 2", "id_number": "987654321"}
        ],
        "total": 2
    }

@app.post("/api/v1/clients")
def create_client(client_data: dict):
    """Create new client - mock implementation"""
    return {
        "id": 999,
        "message": "Client created successfully",
        "data": client_data
    }

@app.get("/api/v1/clients/{client_id}")
def get_client(client_id: int):
    """Get client by ID - mock implementation"""
    return {
        "id": client_id,
        "name": f"Client {client_id}",
        "id_number": f"{client_id:09d}",
        "status": "active"
    }

# Tax data endpoints
@app.get("/api/v1/tax-data/severance-caps")
def get_severance_caps():
    """Get severance payment caps"""
    return {
        "monthly_cap": 41667,
        "annual_cap": 500000,
        "currency": "ILS",
        "year": 2024
    }

@app.get("/api/v1/tax-data/tax-brackets")
def get_tax_brackets():
    """Get tax brackets"""
    return {
        "brackets": [
            {"min": 0, "max": 75960, "rate": 0.10},
            {"min": 75960, "max": 108840, "rate": 0.14},
            {"min": 108840, "max": 174840, "rate": 0.20},
            {"min": 174840, "max": 243720, "rate": 0.31},
            {"min": 243720, "max": 509040, "rate": 0.35},
            {"min": 509040, "max": 663240, "rate": 0.47},
            {"min": 663240, "max": None, "rate": 0.50}
        ],
        "year": 2024
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting clean FastAPI server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
