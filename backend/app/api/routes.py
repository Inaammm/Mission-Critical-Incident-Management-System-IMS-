"""REST API routes for work items, RCA, and dashboard"""

from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import (
    WorkItemResponse,
    WorkItemTransition,
    RCACreate,
    RCAResponse,
    DashboardStats,
)
from app.models.database import WorkItem, RCA, WorkItemStatus, Severity
from app.repositories.connections import get_db
from app.repositories.postgres_repo import (
    WorkItemRepository,
    RCARepository,
    AuditLogRepository,
)
from app.repositories.mongo_repo import SignalRepository
from app.repositories.redis_repo import RedisRepository
from app.workflow.state_machine import get_state
from app.metrics.collector import metrics_collector

router = APIRouter(tags=["incidents"])


# --- Work Items ---
@router.get("/incidents", response_model=list[WorkItemResponse])
async def list_incidents(
    active_only: bool = True, limit: int = 50, db: AsyncSession = Depends(get_db)
):
    repo = WorkItemRepository(db)
    if active_only:
        items = await repo.get_active(limit)
    else:
        items = await repo.get_all(limit)

    # Enrich with SLA remaining
    results = []
    now = datetime.utcnow()
    for item in items:
        resp = WorkItemResponse.model_validate(item)
        if item.sla_deadline and item.status not in (
            WorkItemStatus.CLOSED,
            WorkItemStatus.RESOLVED,
        ):
            resp.sla_remaining_seconds = max(
                0, (item.sla_deadline - now).total_seconds()
            )
        results.append(resp)
    return results


@router.get("/incidents/{incident_id}", response_model=WorkItemResponse)
async def get_incident(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = WorkItemRepository(db)
    item = await repo.get_by_id(incident_id)
    if not item:
        raise HTTPException(status_code=404, detail="Incident not found")
    resp = WorkItemResponse.model_validate(item)
    if item.sla_deadline and item.status not in (
        WorkItemStatus.CLOSED,
        WorkItemStatus.RESOLVED,
    ):
        resp.sla_remaining_seconds = max(
            0, (item.sla_deadline - datetime.utcnow()).total_seconds()
        )
    return resp


@router.get("/incidents/{incident_id}/signals")
async def get_incident_signals(incident_id: UUID, limit: int = 100):
    signals = await SignalRepository.get_by_work_item(str(incident_id), limit)
    return signals


@router.get("/incidents/{incident_id}/audit")
async def get_incident_audit(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = AuditLogRepository(db)
    logs = await repo.get_for_work_item(incident_id)
    return [
        {
            "id": str(log.id),
            "action": log.action,
            "old_value": log.old_value,
            "new_value": log.new_value,
            "performed_by": log.performed_by,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


# --- State Transitions ---
@router.post("/incidents/{incident_id}/transition")
async def transition_incident(
    incident_id: UUID,
    transition: WorkItemTransition,
    db: AsyncSession = Depends(get_db),
):
    repo = WorkItemRepository(db)
    audit_repo = AuditLogRepository(db)

    work_item = await repo.get_by_id(incident_id)
    if not work_item:
        raise HTTPException(status_code=404, detail="Incident not found")

    current_state = get_state(work_item.status)
    target_status = transition.new_status

    # Validate transition
    allowed, reason = current_state.validate_transition(work_item, target_status)
    if not allowed:
        raise HTTPException(status_code=400, detail=reason)

    # Get on_enter effects
    target_state = get_state(target_status)
    extra_fields = target_state.on_enter(work_item)

    old_status = work_item.status.value
    updated = await repo.update_status(incident_id, target_status, **extra_fields)

    # Audit log
    await audit_repo.log(
        incident_id,
        f"STATUS_CHANGE",
        old_value=old_status,
        new_value=target_status.value,
        performed_by=transition.performed_by,
    )

    # Track metrics
    metrics_collector.record_state_transition(old_status, target_status.value)
    if extra_fields.get("mttr_seconds"):
        metrics_collector.record_mttr(extra_fields["mttr_seconds"])

    # Publish WebSocket event
    await RedisRepository.publish_event(
        "incidents:update",
        {
            "id": str(incident_id),
            "old_status": old_status,
            "new_status": target_status.value,
        },
    )

    return {"status": "transitioned", "from": old_status, "to": target_status.value}


# --- RCA ---
@router.post("/incidents/{incident_id}/rca", response_model=RCAResponse)
async def submit_rca(
    incident_id: UUID, rca_data: RCACreate, db: AsyncSession = Depends(get_db)
):
    work_item_repo = WorkItemRepository(db)
    rca_repo = RCARepository(db)
    audit_repo = AuditLogRepository(db)

    work_item = await work_item_repo.get_by_id(incident_id)
    if not work_item:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Check if RCA already exists
    existing = await rca_repo.get_by_work_item(incident_id)
    if existing:
        raise HTTPException(
            status_code=409, detail="RCA already exists for this incident"
        )

    # Validate RCA completeness
    if not all(
        [
            rca_data.root_cause_category,
            rca_data.root_cause_description,
            rca_data.fix_applied,
            rca_data.prevention_steps,
        ]
    ):
        raise HTTPException(status_code=422, detail="All RCA fields are mandatory")

    rca = RCA(
        work_item_id=incident_id,
        incident_start=rca_data.incident_start,
        incident_end=rca_data.incident_end,
        root_cause_category=rca_data.root_cause_category,
        root_cause_description=rca_data.root_cause_description,
        fix_applied=rca_data.fix_applied,
        prevention_steps=rca_data.prevention_steps,
        created_by=rca_data.created_by,
    )

    created_rca = await rca_repo.create(rca)

    # Calculate and store MTTR
    mttr = (rca_data.incident_end - rca_data.incident_start).total_seconds()
    await work_item_repo.update_status(incident_id, work_item.status, mttr_seconds=mttr)

    await audit_repo.log(
        incident_id,
        "RCA_SUBMITTED",
        new_value=f"Category: {rca_data.root_cause_category}",
        performed_by=rca_data.created_by or "engineer",
    )

    return RCAResponse.model_validate(created_rca)


@router.get("/incidents/{incident_id}/rca", response_model=RCAResponse)
async def get_rca(incident_id: UUID, db: AsyncSession = Depends(get_db)):
    repo = RCARepository(db)
    rca = await repo.get_by_work_item(incident_id)
    if not rca:
        raise HTTPException(status_code=404, detail="RCA not found")
    return RCAResponse.model_validate(rca)


# --- Dashboard ---
@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    # Try cache first
    cached = await RedisRepository.get_dashboard_cache()
    if cached:
        return DashboardStats(**cached)

    repo = WorkItemRepository(db)
    data = await repo.get_dashboard_stats()

    stats = DashboardStats(
        total_open=data["stats"].get(WorkItemStatus.OPEN, 0),
        total_investigating=data["stats"].get(WorkItemStatus.INVESTIGATING, 0),
        total_resolved=data["stats"].get(WorkItemStatus.RESOLVED, 0),
        total_closed=data["stats"].get(WorkItemStatus.CLOSED, 0),
        signals_per_second=metrics_collector.get_signals_per_second(),
        avg_mttr_seconds=data["avg_mttr"],
        p0_count=data["severity"].get(Severity.P0, 0),
        p1_count=data["severity"].get(Severity.P1, 0),
        p2_count=data["severity"].get(Severity.P2, 0),
    )

    # Cache for 10 seconds
    await RedisRepository.update_dashboard_cache(stats.model_dump())
    return stats
