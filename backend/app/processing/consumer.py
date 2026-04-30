"""Signal processing consumer with debouncing and circuit breaker"""

import asyncio
import json
from datetime import datetime, timedelta
from uuid import uuid4
from app.repositories.redis_repo import RedisRepository
from app.repositories.mongo_repo import SignalRepository
from app.repositories.connections import async_session
from app.repositories.postgres_repo import WorkItemRepository, AuditLogRepository
from app.models.database import WorkItem, WorkItemStatus, ComponentType, Severity
from app.workflow.alert_strategy import get_alert_strategy
from app.metrics.collector import metrics_collector
from app.config import get_settings

settings = get_settings()

CONSUMER_GROUP = "signal_processors"
CONSUMER_NAME = "processor_1"


# Simple circuit breaker implementation (pybreaker's call_async requires tornado)
class SimpleCircuitBreaker:
    def __init__(self, fail_max=5, reset_timeout=30):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.fail_count = 0
        self.is_open = False
        self._last_failure = None

    async def call(self, func, *args, **kwargs):
        if self.is_open:
            import time

            if (
                self._last_failure
                and (time.time() - self._last_failure) > self.reset_timeout
            ):
                self.is_open = False
                self.fail_count = 0
            else:
                raise CircuitBreakerOpen(f"Circuit breaker is open")
        try:
            result = await func(*args, **kwargs)
            self.fail_count = 0
            return result
        except Exception as e:
            import time

            self.fail_count += 1
            self._last_failure = time.time()
            if self.fail_count >= self.fail_max:
                self.is_open = True
            raise


class CircuitBreakerOpen(Exception):
    pass


mongo_breaker = SimpleCircuitBreaker(fail_max=5, reset_timeout=30)
postgres_breaker = SimpleCircuitBreaker(fail_max=5, reset_timeout=30)


async def process_signal(signal_data: dict) -> None:
    """Process a single signal: debounce, store, create/link work item"""
    component_id = signal_data.get("component_id", "")
    component_type = signal_data.get("component_type", "API")
    timestamp_str = signal_data.get("timestamp", "")
    timestamp = (
        datetime.fromisoformat(timestamp_str) if timestamp_str else datetime.utcnow()
    )

    # Store raw signal in MongoDB (circuit breaker protected)
    raw_signal = {
        "component_id": component_id,
        "component_type": component_type,
        "error_code": signal_data.get("error_code", ""),
        "error_message": signal_data.get("error_message", ""),
        "latency_ms": float(signal_data.get("latency_ms", 0)),
        "metadata": signal_data.get("metadata", ""),
        "timestamp": timestamp,
        "work_item_id": None,
        "ingested_at": datetime.utcnow(),
    }

    try:
        await mongo_breaker.call(SignalRepository.store_signal, raw_signal)
    except CircuitBreakerOpen:
        print(
            f"[CIRCUIT BREAKER] MongoDB breaker OPEN — signal for {component_id} deferred"
        )
        return

    # Debounce: increment counter for this component
    count = await RedisRepository.increment_debounce_counter(component_id)

    # Check if we already have an active work item for this component
    existing_work_item_id = await RedisRepository.get_active_work_item(component_id)

    if existing_work_item_id:
        # Link signal to existing work item
        await SignalRepository.link_signals_to_work_item(
            component_id,
            existing_work_item_id,
            timestamp - timedelta(seconds=settings.debounce_window_seconds),
        )
        # Increment signal count on work item
        try:
            async with async_session() as session:
                repo = WorkItemRepository(session)
                await repo.increment_signal_count(existing_work_item_id)
        except Exception:
            pass
        return

    # Debounce threshold: only create work item at threshold
    if count < settings.debounce_threshold and count > 1:
        # Not yet at threshold, and not first signal — just accumulate
        return

    # Create new work item (first signal OR threshold reached)
    if count == 1 or count == settings.debounce_threshold:
        try:
            await create_work_item(component_id, component_type, signal_data, timestamp)
        except CircuitBreakerOpen:
            print(
                f"[CIRCUIT BREAKER] PostgreSQL breaker OPEN — work item creation deferred"
            )
        except Exception as e:
            print(f"[ERROR] Failed to create work item: {e}")


async def create_work_item(
    component_id: str, component_type_str: str, signal_data: dict, timestamp: datetime
) -> None:
    """Create a new work item and alert"""
    component_type = ComponentType(component_type_str)
    strategy = get_alert_strategy()
    alert = strategy.create_alert(
        component_id, component_type, signal_data.get("error_message", "")
    )

    # Calculate SLA deadline
    sla_minutes = {
        Severity.P0: settings.sla_p0_minutes,
        Severity.P1: settings.sla_p1_minutes,
        Severity.P2: settings.sla_p2_minutes,
        Severity.P3: settings.sla_p2_minutes * 2,
    }
    deadline = datetime.utcnow() + timedelta(
        minutes=sla_minutes.get(alert.severity, 240)
    )

    work_item = WorkItem(
        id=uuid4(),
        component_id=component_id,
        component_type=component_type,
        title=alert.title,
        description=alert.message,
        severity=alert.severity,
        status=WorkItemStatus.OPEN,
        signal_count=1,
        first_signal_at=timestamp,
        sla_deadline=deadline,
    )

    async with async_session() as session:
        repo = WorkItemRepository(session)
        audit_repo = AuditLogRepository(session)
        created = await postgres_breaker.call(repo.create, work_item)

        # Log audit
        await audit_repo.log(
            created.id,
            "CREATED",
            new_value=f"Work item created with severity {alert.severity.value}",
            performed_by="system",
        )

    # Cache the active work item mapping
    await RedisRepository.set_active_work_item(component_id, str(created.id))

    # Link all accumulated signals to this work item
    await SignalRepository.link_signals_to_work_item(
        component_id,
        str(created.id),
        timestamp - timedelta(seconds=settings.debounce_window_seconds),
    )

    # Publish event for WebSocket
    await RedisRepository.publish_event(
        "incidents:new",
        {
            "id": str(created.id),
            "component_id": component_id,
            "severity": alert.severity.value,
            "title": alert.title,
            "status": WorkItemStatus.OPEN.value,
        },
    )

    metrics_collector.record_work_item_created()
    print(f"[ALERT] {alert.channel.upper()}: {alert.title}")


async def consumer_loop():
    """Main consumer loop — reads from Redis Stream and processes signals"""
    await RedisRepository.create_consumer_group(CONSUMER_GROUP)
    print(f"[CONSUMER] Started signal consumer: {CONSUMER_NAME}")

    while True:
        try:
            messages = await RedisRepository.read_from_stream(
                CONSUMER_GROUP, CONSUMER_NAME, count=200, block=1000
            )
            if messages:
                for stream_name, stream_messages in messages:
                    for msg_id, msg_data in stream_messages:
                        await process_signal(msg_data)
                        await RedisRepository.ack_message(CONSUMER_GROUP, msg_id)
        except Exception as e:
            print(f"[CONSUMER ERROR] {e}")
            await asyncio.sleep(1)
