"""OrbiFlare FastAPI application entrypoint.

On startup: initializes the database schema and, if running in demo mode
with an empty database, automatically runs the full pipeline against the
synthetic demo fixtures -- so `uvicorn app.main:app` alone is enough to get
a fully working app with no manual seed step required.
"""
from __future__ import annotations

import logging
import threading

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    agent,
    alerts,
    analytics,
    context as context_routes,
    events,
    facilities,
    firms,
    health,
    map as map_routes,
    observations,
    pipeline as pipeline_routes,
    reference,
    reports,
    thermal_twins,
)
from app.config import get_settings
from app.storage.database import SessionLocal, init_db

logging.basicConfig(level=logging.INFO)
# httpx logs full request URLs at INFO, and the FIRMS URL contains the MAP_KEY -- never let it reach a log.
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


class _RedactKey(logging.Filter):
    """Defence in depth: whatever a library logs, the FIRMS MAP_KEY is replaced before it reaches any handler."""
    def filter(self, record: logging.LogRecord) -> bool:
        key = get_settings().firms_map_key
        if key:
            record.msg = str(record.getMessage()).replace(key, "***")
            record.args = ()
            if record.exc_text:
                record.exc_text = record.exc_text.replace(key, "***")
        return True


for _h in logging.getLogger().handlers:
    _h.addFilter(_RedactKey())
logger = logging.getLogger("orbiflare")
settings = get_settings()

app = FastAPI(
    title="OrbiFlare API",
    description="Explainable thermal behaviour intelligence -- SIH26162",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (health.router, observations.router, events.router, facilities.router, thermal_twins.router,
               analytics.router, alerts.router, reports.router, map_routes.router, agent.router, pipeline_routes.router, reference.router, firms.router, context_routes.router):
    app.include_router(router, prefix="/api")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):  # pragma: no cover
    from fastapi.responses import JSONResponse
    logger.exception("Unhandled error on %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"error": "internal_error", "detail": str(exc)})


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    if settings.orbiflare_mode == "demo":
        from app.storage import repositories as repo
        db = SessionLocal()
        try:
            if not repo.list_events(db):
                logger.info("No events found -- auto-seeding DEMO/SYNTHETIC scenario (ORBIFLARE_MODE=demo).")
                from app.intelligence.pipeline import run_full_pipeline
                result = run_full_pipeline(db, mode="demo")
                logger.info("Demo pipeline complete: %s", result)
        finally:
            db.close()


    if settings.firms_auto_sync and settings.firms_map_key:
        threading.Thread(target=_startup_sync, name="firms-startup-sync", daemon=True).start()


def _startup_sync() -> None:
    """One best-effort live sync at start. A failure is logged and changes nothing (no silent switch to synthetic data)."""
    from app.ingestion import firms_refresh
    db = SessionLocal()
    try:
        summary = firms_refresh.refresh_firms(db)
        logger.info("Startup FIRMS sync: %d received, %d new, %d events", summary["observations_received"], summary["new_observations"], summary["events_total"])
    except firms_refresh.FirmsError as err:
        logger.warning("Startup FIRMS sync failed (%s): %s", err.code, err.message)
    except Exception:  # pragma: no cover
        logger.exception("Startup FIRMS sync failed unexpectedly")
    finally:
        db.close()
