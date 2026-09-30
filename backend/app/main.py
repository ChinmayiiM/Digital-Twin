"""TwinMate AI - FastAPI entry point (Phase 6: + privacy & data control, permissions, access logs, export)."""
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models  # noqa: F401  (registers the tables with Base.metadata)
from app.database import Base, engine, get_db
from app.routers import (dashboard, demo, feedback, goals, observations, preferences, privacy, simulator, tasks,
                         twin, users)

# Creates any missing tables. Existing tables and their data are never touched (safe for Phase 2 databases).
Base.metadata.create_all(bind=engine)

app = FastAPI(title="TwinMate AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://digital-twin-weld-nine.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def _friendly(error: dict) -> str:
    """Turn a Pydantic error into a short human-readable sentence."""
    fields = [str(part) for part in error["loc"] if part not in ("body", "query", "path")]
    label = (fields[-1] if fields else "value").replace("_", " ").capitalize()
    kind = error["type"]
    if kind == "string_too_short":
        return f"{label} cannot be empty"
    if kind == "greater_than":
        return f"{label} must be greater than {error['ctx']['gt']:g}"
    if kind == "greater_than_equal":
        return f"{label} must be {error['ctx']['ge']:g} or more"
    if kind == "string_too_long":
        return f"{label} is too long (maximum {error['ctx']['max_length']} characters)"
    if kind == "less_than_equal":
        return f"{label} must be at most {error['ctx']['le']}"
    if kind == "literal_error":
        return f"{label} must be one of: {error['ctx']['expected']}"
    if kind == "missing":
        return f"{label} is required"
    if kind == "value_error":
        return error["msg"].replace("Value error, ", "")
    return f"{label}: {error['msg']}"


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_request: Request, exc: RequestValidationError):
    messages = [_friendly(e) for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "; ".join(messages), "errors": messages})


app.include_router(users.router)
app.include_router(goals.router)
app.include_router(tasks.router)
app.include_router(preferences.router)
app.include_router(dashboard.router)
app.include_router(observations.router)
app.include_router(twin.router)
app.include_router(demo.router)
app.include_router(simulator.router)
app.include_router(feedback.router)
app.include_router(privacy.router)


@app.get("/")
def root():
    return {"message": "TwinMate AI API is running"}


@app.get("/api/health")
def health_check(db: Session = Depends(get_db)):
    """Runs a real query against SQLite through SQLAlchemy."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "application": "TwinMate AI", "database": "disconnected"},
        )
    return {"status": "ok", "application": "TwinMate AI", "database": "connected"}
