from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.db.session import get_db
from app.api.auth import router as auth_router
from app.api.agents import router as agents_router
from app.api.tasks import router as tasks_router
from app.api.runs import router as runs_router
from app.api.events import router as events_router
from app.api.logs import router as logs_router
from app.api.metrics import router as metrics_router
from app.api.alerts import router as alerts_router
from app.api.audit import router as audit_router
from app.api.analytics import router as analytics_router
from app.api.errors import router as errors_router
from app.api.chat import router as chat_router
from app.models.memory import AgentMemory, AgentMemorySummary
from app.db.session import engine

app = FastAPI(
    title=settings.APP_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    debug=settings.DEBUG,
)

# CORS: only the origins listed in BACKEND_CORS_ORIGINS may call the API from a browser.
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount routers (every router carries its own API_V1_STR prefix)
app.include_router(auth_router)
app.include_router(agents_router)
app.include_router(tasks_router)
app.include_router(runs_router)
app.include_router(events_router)
app.include_router(logs_router)
app.include_router(metrics_router)
app.include_router(alerts_router)
app.include_router(audit_router)
app.include_router(analytics_router)
app.include_router(errors_router)
app.include_router(chat_router)


@app.on_event("startup")
def ensure_agent_memory_table():
    """Create the additive memory table for installations bootstrapped before this feature."""
    AgentMemory.__table__.create(bind=engine, checkfirst=True)
    AgentMemorySummary.__table__.create(bind=engine, checkfirst=True)


@app.get("/health", tags=["System"])
def health_check(db: Session = Depends(get_db)):
    """Health check endpoint confirming backend service status and database ping."""
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": "development" if settings.DEBUG else "production",
        "database": db_status,
    }
