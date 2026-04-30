"""Signal ingestion API with rate limiting"""

from datetime import datetime
from fastapi import APIRouter, HTTPException, status
from app.models.schemas import SignalPayload, SignalBatch
from app.repositories.redis_repo import RedisRepository
from app.metrics.collector import metrics_collector

router = APIRouter(prefix="/signals", tags=["ingestion"])


@router.post("/", status_code=status.HTTP_202_ACCEPTED)
async def ingest_signal(signal: SignalPayload):
    """Ingest a single signal. Rate-limited and buffered via Redis Stream."""
    allowed = await RedisRepository.check_rate_limit()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Try again shortly.",
        )

    signal_data = {
        "component_id": signal.component_id,
        "component_type": signal.component_type.value,
        "error_code": signal.error_code or "",
        "error_message": signal.error_message,
        "latency_ms": str(signal.latency_ms or 0),
        "metadata": str(signal.metadata or {}),
        "timestamp": (signal.timestamp or datetime.utcnow()).isoformat(),
    }

    await RedisRepository.push_to_stream(signal_data)
    metrics_collector.record_signal_ingested()

    return {"status": "accepted", "component_id": signal.component_id}


@router.post("/batch", status_code=status.HTTP_202_ACCEPTED)
async def ingest_batch(batch: SignalBatch):
    """Ingest a batch of signals."""
    allowed = await RedisRepository.check_rate_limit()
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded."
        )

    for signal in batch.signals:
        signal_data = {
            "component_id": signal.component_id,
            "component_type": signal.component_type.value,
            "error_code": signal.error_code or "",
            "error_message": signal.error_message,
            "latency_ms": str(signal.latency_ms or 0),
            "metadata": str(signal.metadata or {}),
            "timestamp": (signal.timestamp or datetime.utcnow()).isoformat(),
        }
        await RedisRepository.push_to_stream(signal_data)
        metrics_collector.record_signal_ingested()

    return {"status": "accepted", "count": len(batch.signals)}
