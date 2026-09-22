"""OrbiFlare FastAPI application entrypoint.

On startup: initializes the database schema and, if running in demo mode
with an empty database, automatically runs the full pipeline against the
synthetic demo fixtures -- so `uvicorn app.main:app` alone is enough to get
a fully working app with no manual seed step required.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    agent,
    alerts,
    analytics,
    events,
    facilities,
    health,
    map as map_routes,
    observations,
    pipeline as pipeline_routes,
    reports,
    thermal_twins,
)
from app.config import get_settings
from app.storage.database import SessionLocal, init_db

logging.basicConfig(level=logging.INFO)
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
               analytics.router, alerts.router, reports.router, map_routes.router, agent.router, pipeline_routes.router):
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
