"""
FastAPI application entrypoint
"""
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# הגדרת לוגר בסיסית (קונסול)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

BUILT_AT_UTC = datetime.utcnow().isoformat() + "Z"

# הפעלת לוגינג מתקדם לקבצים (app.log, app.json, fixation.log)
try:
    from app.logging_config import setup_logging
    setup_logging()
except Exception as e:
    logger.warning("Could not initialize advanced logging: %s", e)

import app.models  # noqa: F401  # מבטיח שכל המודלים נטענים, ל־metadata.create_all
from app.database import engine, Base
from app.config import cors_allow_origins, cors_allow_origin_regex, cors_allow_credentials
from app.routers import (
    fixation,
    files,
    employment,
    pension_fund,
    additional_income,
    capital_asset,
    income_integration,
    cashflow_generation,
    report_generation,
    scenario_compare,
    case_detection,
    clients,
    grant,
    tax_data,
    indexation,
    rights_fixation,
    tax_calculation,
    pension_portfolio,
    snapshot,
    retirement_age,
    annuity_coefficient,
    system_health,
    calculation,
    public_chat,
    reports,
)

try:
    from app.routers import llm_chat
except Exception:
    llm_chat = None
from app.routers.employment import router as employment_router
from app.routers.employment_api import router as employment_api_router
from app.routers.scenarios import router as scenarios_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database tables on application startup"""
    Base.metadata.create_all(bind=engine)

    from app.database import ensure_client_public_chat_credit_schema

    ensure_client_public_chat_credit_schema(engine)
    
    # אימות תקינות המערכת
    logger.info("=" * 60)
    logger.info("🚀 Starting Retirement Planning System")
    logger.info("=" * 60)
    
    from app.core.system_validator import run_system_validation_background

    asyncio.create_task(asyncio.to_thread(run_system_validation_background))
    
    logger.info("=" * 60)
    
    yield
    # Cleanup code can go here (if needed)

# Create FastAPI app
app = FastAPI(
    title="Retirement Planning System",
    description="API for retirement planning system",
    version="1.0.9",
    lifespan=lifespan,
)

from app.core.system_access import SystemAccessMiddleware
app.add_middleware(SystemAccessMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allow_origins(),
    allow_origin_regex=cors_allow_origin_regex(),
    allow_credentials=cors_allow_credentials(),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add ProxyHeadersMiddleware to trust headers from Railway load balancer
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.middleware.trace_id import TraceIdMiddleware
import os

app.add_middleware(TraceIdMiddleware)

if os.getenv("STREAM_TRACE_LOGGER_ENABLED") == "1":
    from app.middleware.stream_trace_logger import StreamTraceLoggerMiddleware

    app.add_middleware(StreamTraceLoggerMiddleware)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["*"])

# Include routers
app.include_router(clients.router)  # clients router already has /api/v1/clients prefix
app.include_router(employment.router)  # employment router already has /api/v1/clients prefix
app.include_router(employment_router, prefix="/api/v1", tags=["current_employer"])
app.include_router(employment_api_router)  # legacy Employment API (/api/v1/clients/.../employment/...)
app.include_router(fixation.router,   prefix="/api/v1", tags=["fixation"])
app.include_router(pension_fund.router)
app.include_router(additional_income.router, prefix="/api/v1")
app.include_router(capital_asset.router, prefix="/api/v1")
app.include_router(income_integration.router, prefix="/api/v1")
app.include_router(cashflow_generation.router)
app.include_router(report_generation.router)
app.include_router(scenarios_router)  # scenarios router already has /api/v1/clients prefix
app.include_router(scenario_compare.router)
app.include_router(case_detection.router, prefix="/api/v1")
app.include_router(grant.router, prefix="/api/v1")  # Grant router
app.include_router(tax_data.router, prefix="/api/v1/tax-data", tags=["tax-data"])
app.include_router(indexation.router, prefix="/api/v1/indexation", tags=["indexation"])
app.include_router(rights_fixation.router, tags=["rights-fixation"])
app.include_router(tax_calculation.router, tags=["tax-calculation"])
app.include_router(pension_portfolio.router, prefix="/api/v1", tags=["pension-portfolio"])
app.include_router(snapshot.router)  # snapshot router already has /api/v1/clients prefix
app.include_router(retirement_age.router, prefix="/api/v1", tags=["retirement-age"])
app.include_router(annuity_coefficient.router, prefix="/api/v1/annuity-coefficient", tags=["annuity-coefficient"])
app.include_router(system_health.router, tags=["system-health"])
app.include_router(calculation.router)
if llm_chat is not None:
    app.include_router(llm_chat.router)
app.include_router(public_chat.router)
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

frontend_dist_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
frontend_assets_dir = frontend_dist_dir / "assets"
if frontend_assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_assets_dir)), name="frontend-assets")


@app.get("/")
def read_root():
    """Root endpoint"""
    index_html = frontend_dist_dir / "index.html"
    if index_html.exists():
        return FileResponse(str(index_html), media_type="text/html")
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
    return {
        "status": "ok",
        "version": "1.0.9",
        "git_sha": os.getenv("GIT_SHA") or os.getenv("RAILWAY_GIT_COMMIT_SHA") or "unknown",
        "build_time": os.getenv("BUILD_TIME") or "unknown",
    }

@app.get("/api/v1/health")
def health_check_v1():
    """Health check endpoint with API prefix"""
    return {"status": "ok"}


@app.get("/api/v1/version")
def version_v1():
    git_sha = (
        os.getenv("RAILWAY_GIT_COMMIT_SHA")
        or os.getenv("RAILWAY_COMMIT_SHA")
        or os.getenv("GITHUB_SHA")
        or "unknown"
    )
    railway_deploy_id = os.getenv("RAILWAY_DEPLOYMENT_ID") or "unknown"
    return {
        "git_sha": git_sha,
        "railway_deploy_id": railway_deploy_id,
        "built_at_utc": BUILT_AT_UTC,
        "service": "retire-production",
    }


@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404)
    if ".." in Path(full_path).parts:
        raise HTTPException(status_code=404)
    index_html = frontend_dist_dir / "index.html"
    if not index_html.exists():
        raise HTTPException(status_code=404)
    candidate = frontend_dist_dir / full_path
    if candidate.is_file():
        return FileResponse(str(candidate))
    return FileResponse(str(index_html), media_type="text/html")




