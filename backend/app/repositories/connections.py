"""Database connection management"""

import asyncio
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as aioredis
from app.config import get_settings
from app.models.database import Base


settings = get_settings()

# PostgreSQL
engine = create_async_engine(settings.postgres_url, pool_size=20, max_overflow=10)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# MongoDB
mongo_client = AsyncIOMotorClient(settings.mongodb_url)
mongo_db = mongo_client["ims"]
signals_collection = mongo_db["raw_signals"]

# Redis
redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)


async def init_db():
    """Create all tables and setup TimescaleDB hypertable"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create TimescaleDB hypertable for time-series aggregations
        try:
            await conn.execute(
                text(
                    "SELECT create_hypertable('signal_metrics', 'time', if_not_exists => TRUE);"
                )
            )
        except Exception:
            pass  # Table may not exist yet or already a hypertable


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
