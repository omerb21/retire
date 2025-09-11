"""
FastAPI application entrypoint
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401  # מבטיח שכל המודלים נטענים, ל־metadata.create_all
from app.database import engine, Base
from app.routers import client, fixation, files, employment, report, current_employer, pension_fund, pension_scenario, additional_income, capital_asset, income_integration, cashflow_generation, report_generation, scenario_compare, case_detection, clients, scenarios, grant, reports, tax_data, indexation
from routes.clients import router as new_clients_router
from routes.reports import router as reports_router

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
    allow_origins=["*"],          # מאפשר גם Origin=null של file:// וגם כל פורט מקומי
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,      # חייב להיות False כדי לאפשר "*"
)

# Include routers
app.include_router(client.router)      # client router already has /api/v1/clients prefix
app.include_router(employment.router)  # employment router already has /api/v1/clients prefix
app.include_router(current_employer.router, prefix="/api/v1", tags=["current_employer"])
# app.include_router(calc.router,       prefix="/api/v1", tags=["calc"])  # Disabled - conflicts with scenarios router
app.include_router(report.router,     prefix="/api/v1", tags=["reports"])
app.include_router(fixation.router,   prefix="/api/v1", tags=["fixation"])
app.include_router(pension_fund.router)
# app.include_router(pension_scenario.router)  # Disabled - conflicts with scenarios router
app.include_router(additional_income.router, prefix="/api/v1")
app.include_router(capital_asset.router, prefix="/api/v1")
app.include_router(income_integration.router, prefix="/api/v1")
app.include_router(cashflow_generation.router)
app.include_router(report_generation.router)
app.include_router(scenario_compare.router)
app.include_router(case_detection.router, prefix="/api/v1")
app.include_router(grant.router, prefix="/api/v1")  # Grant router
app.include_router(reports.router, prefix="/api/v1")  # Reports router
app.include_router(tax_data.router, prefix="/api/v1/tax-data", tags=["tax-data"])
app.include_router(indexation.router, prefix="/api/v1/indexation", tags=["indexation"])

# New API routers
app.include_router(clients.router)     # New clients router with CRUD
app.include_router(scenarios.router)   # Fixed scenarios router
app.include_router(new_clients_router, prefix="/api/v1")  # Sprint A clients router
# app.include_router(new_scenarios_router, prefix="/api/v1")  # Old scenarios router - disabled to avoid conflict
app.include_router(reports_router)  # Sprint E reports router

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def read_root():
    """Root endpoint"""
    return {"message": "Welcome to Retirement Planning System API"}


@app.get("/ui")
def ui_redirect():
    """Permanent UI for operations"""
    from fastapi.responses import HTMLResponse
    with open("app/static/index.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    return HTMLResponse(content=html_content)


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

@app.get("/api/v1/health")
def health_check_v1():
    """Health check endpoint with API prefix"""
    return {"status": "ok"}




