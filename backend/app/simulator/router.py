"""Signal simulator for load testing and demos"""

import asyncio
import random
from datetime import datetime
from fastapi import APIRouter
from app.models.database import ComponentType
from app.repositories.redis_repo import RedisRepository
from app.metrics.collector import metrics_collector

router = APIRouter(prefix="/simulate", tags=["simulator"])

COMPONENTS = [
    ("API_GATEWAY_01", ComponentType.API),
    ("API_GATEWAY_02", ComponentType.API),
    ("MCP_HOST_PRIMARY", ComponentType.MCP_HOST),
    ("CACHE_CLUSTER_01", ComponentType.CACHE),
    ("CACHE_CLUSTER_02", ComponentType.CACHE),
    ("QUEUE_BROKER_01", ComponentType.QUEUE),
    ("RDBMS_PRIMARY", ComponentType.RDBMS),
    ("RDBMS_REPLICA_01", ComponentType.RDBMS),
    ("NOSQL_CLUSTER_01", ComponentType.NOSQL),
]

ERROR_MESSAGES = [
    "Connection timeout after 30s",
    "Out of memory: unable to allocate 256MB",
    "Disk I/O error on /dev/sda1",
    "Connection refused: max connections reached",
    "Replication lag exceeded 10s threshold",
    "Query execution timeout: 60s exceeded",
    "SSL handshake failure",
    "Rate limit exceeded on upstream",
    "Health check failed: 3 consecutive failures",
    "Deadlock detected on table locks",
]


@router.post("/burst")
async def simulate_burst(
    component_id: str = None,
    signals_count: int = 100,
    delay_ms: int = 10,
):
    """Simulate a burst of signals for a specific or random component"""
    if component_id:
        comp_type = next(
            (ct for cid, ct in COMPONENTS if cid == component_id), ComponentType.API
        )
        target = (component_id, comp_type)
    else:
        target = random.choice(COMPONENTS)

    sent = 0
    for _ in range(signals_count):
        signal_data = {
            "component_id": target[0],
            "component_type": target[1].value,
            "error_code": f"ERR_{random.randint(1000, 9999)}",
            "error_message": random.choice(ERROR_MESSAGES),
            "latency_ms": str(random.uniform(100, 5000)),
            "metadata": "{}",
            "timestamp": datetime.utcnow().isoformat(),
        }
        await RedisRepository.push_to_stream(signal_data)
        metrics_collector.record_signal_ingested()
        sent += 1
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)

    return {
        "status": "completed",
        "component_id": target[0],
        "signals_sent": sent,
    }


@router.post("/flood")
async def simulate_flood(
    duration_seconds: int = 10,
    signals_per_second: int = 1000,
):
    """Simulate high-throughput flood across multiple components"""
    total_sent = 0
    end_time = asyncio.get_event_loop().time() + duration_seconds
    batch_size = signals_per_second // 10  # Send in batches every 100ms

    async def send_batch():
        nonlocal total_sent
        while asyncio.get_event_loop().time() < end_time:
            tasks = []
            for _ in range(batch_size):
                target = random.choice(COMPONENTS)
                signal_data = {
                    "component_id": target[0],
                    "component_type": target[1].value,
                    "error_code": f"ERR_{random.randint(1000, 9999)}",
                    "error_message": random.choice(ERROR_MESSAGES),
                    "latency_ms": str(random.uniform(50, 3000)),
                    "metadata": "{}",
                    "timestamp": datetime.utcnow().isoformat(),
                }
                tasks.append(RedisRepository.push_to_stream(signal_data))
                metrics_collector.record_signal_ingested()
                total_sent += 1
            await asyncio.gather(*tasks)
            await asyncio.sleep(0.1)

    asyncio.create_task(send_batch())

    return {
        "status": "flood_started",
        "duration_seconds": duration_seconds,
        "target_rate": signals_per_second,
    }
