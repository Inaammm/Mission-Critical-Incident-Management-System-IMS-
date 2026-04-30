"""MongoDB repository for raw signal storage"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from tenacity import retry, stop_after_attempt, wait_exponential

from app.repositories.connections import signals_collection


class SignalRepository:
    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def store_signal(signal: dict) -> str:
        result = await signals_collection.insert_one(signal)
        return str(result.inserted_id)

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def store_signals_batch(signals: list[dict]) -> list[str]:
        if not signals:
            return []
        result = await signals_collection.insert_many(signals)
        return [str(id) for id in result.inserted_ids]

    @staticmethod
    async def get_by_work_item(work_item_id: str, limit: int = 100) -> list[dict]:
        cursor = (
            signals_collection.find({"work_item_id": work_item_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        signals = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            signals.append(doc)
        return signals

    @staticmethod
    async def get_by_component(component_id: str, limit: int = 100) -> list[dict]:
        cursor = (
            signals_collection.find({"component_id": component_id})
            .sort("timestamp", -1)
            .limit(limit)
        )
        signals = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            signals.append(doc)
        return signals

    @staticmethod
    async def link_signals_to_work_item(
        component_id: str, work_item_id: str, since: datetime
    ) -> int:
        result = await signals_collection.update_many(
            {
                "component_id": component_id,
                "timestamp": {"$gte": since},
                "work_item_id": None,
            },
            {"$set": {"work_item_id": work_item_id}},
        )
        return result.modified_count
