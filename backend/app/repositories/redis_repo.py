"""Redis repository for caching, debouncing, and pub/sub"""

import json
from datetime import datetime
from typing import Optional

from app.repositories.connections import redis_client
from app.config import get_settings

settings = get_settings()

STREAM_KEY = "signals:stream"
DASHBOARD_KEY = "dashboard:state"
DEBOUNCE_PREFIX = "debounce:"
WORK_ITEM_MAP_PREFIX = "workitem:component:"


class RedisRepository:
    @staticmethod
    async def push_to_stream(signal_data: dict) -> str:
        """Push signal to Redis Stream for async processing"""
        # Serialize datetime objects
        data = {
            k: (
                v.isoformat()
                if isinstance(v, datetime)
                else str(v)
                if v is not None
                else ""
            )
            for k, v in signal_data.items()
        }
        msg_id = await redis_client.xadd(STREAM_KEY, data, maxlen=100000)
        return msg_id

    @staticmethod
    async def read_from_stream(
        consumer_group: str, consumer_name: str, count: int = 100, block: int = 1000
    ) -> list:
        """Read signals from stream as consumer group"""
        try:
            messages = await redis_client.xreadgroup(
                groupname=consumer_group,
                consumername=consumer_name,
                streams={STREAM_KEY: ">"},
                count=count,
                block=block,
            )
            return messages
        except Exception:
            return []

    @staticmethod
    async def create_consumer_group(group_name: str) -> None:
        """Create consumer group if not exists"""
        try:
            await redis_client.xgroup_create(
                STREAM_KEY, group_name, id="0", mkstream=True
            )
        except Exception:
            pass  # Group already exists

    @staticmethod
    async def ack_message(group_name: str, msg_id: str) -> None:
        await redis_client.xack(STREAM_KEY, group_name, msg_id)

    # --- Debouncing ---
    @staticmethod
    async def increment_debounce_counter(component_id: str) -> int:
        """Increment signal count for component in debounce window. Returns new count."""
        key = f"{DEBOUNCE_PREFIX}{component_id}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, settings.debounce_window_seconds)
        return count

    @staticmethod
    async def get_debounce_count(component_id: str) -> int:
        key = f"{DEBOUNCE_PREFIX}{component_id}"
        val = await redis_client.get(key)
        return int(val) if val else 0

    # --- Work Item Component Mapping ---
    @staticmethod
    async def set_active_work_item(component_id: str, work_item_id: str) -> None:
        """Map component to its active work item"""
        key = f"{WORK_ITEM_MAP_PREFIX}{component_id}"
        await redis_client.set(
            key, work_item_id, ex=settings.debounce_window_seconds * 2
        )

    @staticmethod
    async def get_active_work_item(component_id: str) -> Optional[str]:
        key = f"{WORK_ITEM_MAP_PREFIX}{component_id}"
        return await redis_client.get(key)

    # --- Dashboard Cache ---
    @staticmethod
    async def update_dashboard_cache(stats: dict) -> None:
        await redis_client.set(DASHBOARD_KEY, json.dumps(stats), ex=10)

    @staticmethod
    async def get_dashboard_cache() -> Optional[dict]:
        data = await redis_client.get(DASHBOARD_KEY)
        return json.loads(data) if data else None

    # --- Pub/Sub ---
    @staticmethod
    async def publish_event(channel: str, event: dict) -> None:
        await redis_client.publish(channel, json.dumps(event, default=str))

    # --- Rate Limiting (Token Bucket) ---
    @staticmethod
    async def check_rate_limit(
        key: str = "ratelimit:signals", max_tokens: int = None, refill_rate: int = None
    ) -> bool:
        """Simple sliding window rate limiter. Returns True if allowed."""
        if max_tokens is None:
            max_tokens = settings.rate_limit_burst
        if refill_rate is None:
            refill_rate = settings.rate_limit_signals_per_second

        now = datetime.utcnow().timestamp()
        window_start = now - 1.0  # 1 second window

        pipe = redis_client.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, 2)
        results = await pipe.execute()

        current_count = results[1]
        return current_count < max_tokens
