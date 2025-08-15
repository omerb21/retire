"""
FastAPI application entrypoint
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  # מבטיח שכל המודלים נטענים, ל־metadata.create_all
from app.database import engine, Base
from app.routers import client, fixation, files, employment, calc, report, current_employer, pension_fund

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on application startup"""
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup code can go here (if needed)

# Create FastAPI app
app = FastAPI(
    title="Retirement Planning System",
    description="API for retirement planning system",
    version="1.0.0",
    lifespan=lifespan,
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
app.include_router(client.router)      # client router already has /api/v1/clients prefix
app.include_router(employment.router)  # employment router already has /api/v1/clients prefix
app.include_router(current_employer.router, prefix="/api/v1", tags=["current_employer"])
app.include_router(calc.router,       prefix="/api/v1", tags=["calc"])
app.include_router(report.router,     prefix="/api/v1", tags=["reports"])
app.include_router(fixation.router,   prefix="/api/v1", tags=["fixation"])
app.include_router(pension_fund.router)

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


@app.on_event("startup")
def _init_db():
    """Initialize database tables on application startup"""
    Base.metadata.create_all(bind=engine)


