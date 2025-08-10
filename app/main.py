"""
FastAPI application entrypoint
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base
from app.routers import client, fixation, files, employment, calc, report

# Create FastAPI app
app = FastAPI(
    title="Retirement Planning System",
    description="API for retirement planning system",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins in development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(client.router)
app.include_router(fixation.router, prefix="/api/v1", tags=["fixation"])
app.include_router(files.router)
app.include_router(calc.router, prefix="/api/v1", tags=["calc"])
app.include_router(employment.router)
app.include_router(report.router, prefix="/api/v1/reports", tags=["reports"])

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "Welcome to Retirement Planning System API"}


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}


