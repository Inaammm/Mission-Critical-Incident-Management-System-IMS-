"""Main FastAPI application"""

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.repositories.connections import init_db, redis_client, mongo_client, engine
from app.ingestion.router import router as ingestion_router
from app.api.routes import router as api_router
from app.api.websocket import router as ws_router
from app.simulator.router import router as simulator_router
from app.processing.consumer import consumer_loop
from app.metrics.collector import metrics_collector, print_throughput_loop

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"[IMS] Starting {settings.app_name}...")
    await init_db()
    print("[IMS] Database initialized")

    # Start background tasks
    consumer_task = asyncio.create_task(consumer_loop())
    metrics_task = asyncio.create_task(print_throughput_loop())
    print("[IMS] Background tasks started")

    yield

    # Shutdown
    consumer_task.cancel()
    metrics_task.cancel()
    await engine.dispose()
    await redis_client.close()
    mongo_client.close()
    print("[IMS] Shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description="Mission-Critical Incident Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(ingestion_router)
app.include_router(api_router)
app.include_router(ws_router)
app.include_router(simulator_router)


# Health endpoint
@app.get("/health")
async def health_check():
    health = {
        "status": "healthy",
        "postgres": "unknown",
        "mongodb": "unknown",
        "redis": "unknown",
    }

    # Check Redis
    try:
        await redis_client.ping()
        health["redis"] = "healthy"
    except Exception:
        health["redis"] = "unhealthy"
        health["status"] = "degraded"

    # Check MongoDB
    try:
        await mongo_client.admin.command("ping")
        health["mongodb"] = "healthy"
    except Exception:
        health["mongodb"] = "unhealthy"
        health["status"] = "degraded"

    # Check PostgreSQL
    try:
        from sqlalchemy import text
        from app.repositories.connections import async_session

        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        health["postgres"] = "healthy"
    except Exception:
        health["postgres"] = "unhealthy"
        health["status"] = "degraded"

    health["uptime_seconds"] = metrics_collector.uptime_seconds
    health["signals_ingested_total"] = metrics_collector.total_signals
    health["signals_per_second"] = metrics_collector.get_signals_per_second()

    return health


# Prometheus metrics endpoint
@app.get("/metrics")
async def prometheus_metrics():
    return Response(
        content=metrics_collector.get_prometheus_metrics(),
        media_type=metrics_collector.get_content_type(),
    )
