"""PostgreSQL repository for Work Items and RCA"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, stop_after_attempt, wait_exponential

from app.models.database import WorkItem, RCA, AuditLog, WorkItemStatus, SignalMetric


class WorkItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def create(self, work_item: WorkItem) -> WorkItem:
        self.session.add(work_item)
        await self.session.commit()
        await self.session.refresh(work_item)
        return work_item

    async def get_by_id(self, work_item_id: UUID) -> Optional[WorkItem]:
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(WorkItem)
            .where(WorkItem.id == work_item_id)
            .options(selectinload(WorkItem.rca))
        )
        return result.scalar_one_or_none()

    async def get_active(self, limit: int = 50) -> list[WorkItem]:
        result = await self.session.execute(
            select(WorkItem)
            .where(WorkItem.status != WorkItemStatus.CLOSED)
            .order_by(WorkItem.severity, WorkItem.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[WorkItem]:
        result = await self.session.execute(
            select(WorkItem)
            .order_by(WorkItem.severity, WorkItem.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def update_status(
        self, work_item_id: UUID, status: WorkItemStatus, **kwargs
    ) -> WorkItem:
        work_item = await self.get_by_id(work_item_id)
        if not work_item:
            raise ValueError(f"Work item {work_item_id} not found")
        work_item.status = status
        work_item.updated_at = datetime.utcnow()
        for key, value in kwargs.items():
            if hasattr(work_item, key):
                setattr(work_item, key, value)
        await self.session.commit()
        await self.session.refresh(work_item)
        return work_item

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def increment_signal_count(self, work_item_id: UUID) -> None:
        await self.session.execute(
            update(WorkItem)
            .where(WorkItem.id == work_item_id)
            .values(
                signal_count=WorkItem.signal_count + 1, updated_at=datetime.utcnow()
            )
        )
        await self.session.commit()

    async def get_dashboard_stats(self) -> dict:
        result = await self.session.execute(
            select(WorkItem.status, func.count(WorkItem.id)).group_by(WorkItem.status)
        )
        stats = {row[0]: row[1] for row in result.all()}
        severity_result = await self.session.execute(
            select(WorkItem.severity, func.count(WorkItem.id))
            .where(WorkItem.status != WorkItemStatus.CLOSED)
            .group_by(WorkItem.severity)
        )
        severity_stats = {row[0]: row[1] for row in severity_result.all()}
        mttr_result = await self.session.execute(
            select(func.avg(WorkItem.mttr_seconds)).where(
                WorkItem.mttr_seconds.isnot(None)
            )
        )
        avg_mttr = mttr_result.scalar()
        return {
            "stats": stats,
            "severity": severity_stats,
            "avg_mttr": avg_mttr,
        }


class RCARepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def create(self, rca: RCA) -> RCA:
        self.session.add(rca)
        await self.session.commit()
        await self.session.refresh(rca)
        return rca

    async def get_by_work_item(self, work_item_id: UUID) -> Optional[RCA]:
        result = await self.session.execute(
            select(RCA).where(RCA.work_item_id == work_item_id)
        )
        return result.scalar_one_or_none()


class AuditLogRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(
        self,
        work_item_id: UUID,
        action: str,
        old_value: str = None,
        new_value: str = None,
        performed_by: str = "system",
    ) -> None:
        entry = AuditLog(
            work_item_id=work_item_id,
            action=action,
            old_value=old_value,
            new_value=new_value,
            performed_by=performed_by,
        )
        self.session.add(entry)
        await self.session.commit()

    async def get_for_work_item(self, work_item_id: UUID) -> list[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.work_item_id == work_item_id)
            .order_by(AuditLog.created_at)
        )
        return list(result.scalars().all())
