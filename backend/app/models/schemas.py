"""Pydantic schemas for API request/response"""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from app.models.database import WorkItemStatus, Severity, ComponentType


# --- Signal Schemas ---
class SignalPayload(BaseModel):
    component_id: str = Field(..., json_schema_extra={"example": "CACHE_CLUSTER_01"})
    component_type: ComponentType
    error_code: Optional[str] = None
    error_message: str
    latency_ms: Optional[float] = None
    metadata: Optional[dict] = None
    timestamp: Optional[datetime] = None


class SignalBatch(BaseModel):
    signals: list[SignalPayload]


# --- Work Item Schemas ---
class WorkItemCreate(BaseModel):
    component_id: str
    component_type: ComponentType
    title: str
    description: Optional[str] = None
    severity: Severity


class WorkItemResponse(BaseModel):
    id: UUID
    component_id: str
    component_type: ComponentType
    title: str
    description: Optional[str] = None
    severity: Severity
    status: WorkItemStatus
    assigned_to: Optional[str] = None
    signal_count: int
    first_signal_at: datetime
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    mttr_seconds: Optional[float] = None
    sla_deadline: Optional[datetime] = None
    sla_remaining_seconds: Optional[float] = None

    class Config:
        from_attributes = True


class WorkItemTransition(BaseModel):
    new_status: WorkItemStatus
    performed_by: str = "system"
    comment: Optional[str] = None


# --- RCA Schemas ---
class RCACreate(BaseModel):
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str = Field(
        ..., json_schema_extra={"example": "Infrastructure"}
    )
    root_cause_description: str = Field(..., min_length=10)
    fix_applied: str = Field(..., min_length=10)
    prevention_steps: str = Field(..., min_length=10)
    created_by: Optional[str] = "engineer"


class RCAResponse(BaseModel):
    id: UUID
    work_item_id: UUID
    incident_start: datetime
    incident_end: datetime
    root_cause_category: str
    root_cause_description: str
    fix_applied: str
    prevention_steps: str
    created_at: datetime
    created_by: Optional[str]

    class Config:
        from_attributes = True


# --- Dashboard ---
class DashboardStats(BaseModel):
    total_open: int = 0
    total_investigating: int = 0
    total_resolved: int = 0
    total_closed: int = 0
    signals_per_second: float = 0.0
    avg_mttr_seconds: Optional[float] = None
    p0_count: int = 0
    p1_count: int = 0
    p2_count: int = 0


# --- Health ---
class HealthResponse(BaseModel):
    status: str
    postgres: str
    mongodb: str
    redis: str
    uptime_seconds: float
    signals_ingested_total: int
    signals_per_second: float
