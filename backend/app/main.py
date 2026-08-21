"""
FastAPI main app setup.

Lifecycle:
  1. Startup: init DB, start job queue worker, validate dependencies
  2. Request: route ke API endpoint
  3. Shutdown: stop job queue worker, cleanup
"""
from contextlib import asynccontextmanager
import asyncio
import time
import uuid
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from loguru import logger
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal, init_db, recover_jobs_after_startup
from app.services.job_dispatcher import enqueue_job
from app.services.job_queue import get_job_queue
from app.services.maintenance import maintenance_loop
from app.core.pipeline.metadata_gen import test_ollama_connection
from app.api.routes import auth, videos, jobs, clips, system


_file_logging_configured = False


def configure_file_logging() -> None:
    """Add one rotating file sink while retaining Uvicorn's normal console logs."""
    global _file_logging_configured
    if _file_logging_configured:
        return
    logger.add(
        settings.log_dir / "clipgen.log",
        rotation=settings.log_rotation,
        retention=f"{settings.log_retention_days} days",
        level=settings.log_level.upper(),
        enqueue=True,
        serialize=settings.log_json,
    )
    _file_logging_configured = True


# Lifecycle context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup dan shutdown logic."""
    # --- Startup ---
    configure_file_logging()
    app.state.started_at = datetime.utcnow()
    logger.info("🚀 Startup ClipGen Backend")
    
    # 1. Init database
    try:
        init_db()
        logger.info("✅ Database initialized")
        recovery_report = recover_jobs_after_startup()
        if recovery_report.failed_jobs:
            logger.warning(
                "Recovered "
                f"{recovery_report.failed_jobs} interrupted jobs, with "
                f"{len(recovery_report.retry_job_ids)} replacement jobs queued"
            )
    except Exception as e:
        logger.error(f"❌ Database init failed: {e}")
        raise
    
    # 2. Validate dependencies
    try:
        ollama_ok = test_ollama_connection()
        if ollama_ok:
            logger.info("✅ Ollama connection OK")
        else:
            logger.warning("⚠️  Ollama tidak tersedia, metadata generation akan fallback ke default")
    except Exception as e:
        logger.warning(f"⚠️  Ollama check error: {e}")
    
    # 3. Start job queue worker
    job_queue = get_job_queue()
    await job_queue.start_worker()
    logger.info("✅ Job queue worker started")
    if settings.requeue_pending_jobs_on_startup and recovery_report.pending_job_ids:
        for job_id in recovery_report.pending_job_ids:
            await enqueue_job(job_id)
        logger.warning(
            "Requeued "
            f"{len(recovery_report.pending_job_ids)} pending jobs after startup"
        )
    for job_id in recovery_report.retry_job_ids:
        await enqueue_job(job_id)
    maintenance_task = asyncio.create_task(maintenance_loop())
    app.state.maintenance_task = maintenance_task
    logger.info("✅ Maintenance worker started")
    
    yield
    
    # --- Shutdown ---
    logger.info("🛑 Shutdown ClipGen Backend")
    maintenance_task.cancel()
    try:
        await maintenance_task
    except asyncio.CancelledError:
        pass
    logger.info("✅ Maintenance worker stopped")
    await job_queue.stop_worker()
    logger.info("✅ Job queue worker stopped")


# Create FastAPI app
app = FastAPI(
    title="ClipGen API",
    description="Personal AI Video Assistant untuk auto-generate short clips",
    version=settings.app_version,
    lifespan=lifespan,
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach a request id to logs and responses without logging sensitive bodies."""

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.bind(request_id=request_id, method=request.method, path=request.url.path).exception(
                "Request failed"
            )
            raise
        response.headers["X-Request-ID"] = request_id
        logger.bind(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 1),
        ).info("HTTP request completed")
        return response

# --- CORS untuk frontend local dev ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],  # Next.js dev ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

# --- Include routers ---
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(videos.router, prefix="/api/videos", tags=["videos"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(clips.router, prefix="/api/clips", tags=["clips"])
app.include_router(system.router, prefix="/api/system", tags=["system"])


# --- Health check ---
@app.get("/health")
async def health():
    """Health check endpoint untuk monitoring."""
    job_queue = get_job_queue()
    return {
        "status": "ok",
        "queue": job_queue.status(),
        "version": app.version,
    }


@app.get("/health/live")
async def liveness():
    """Liveness probe: the HTTP process is responsive."""
    return {"status": "ok", "version": app.version}


@app.get("/health/ready")
async def readiness():
    """Readiness probe: database is reachable; Ollama is reported but optional."""
    database_ready = False
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        database_ready = True
    except Exception as error:
        logger.error(f"Readiness database check failed: {error}")

    ollama_ready = await asyncio.to_thread(test_ollama_connection)
    return {
        "status": "ok" if database_ready else "unavailable",
        "database": database_ready,
        "ollama": ollama_ready,
        "queue": get_job_queue().status(),
    }


# --- Global error handler ---
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # auto-reload saat dev
        log_level="info",
    )
