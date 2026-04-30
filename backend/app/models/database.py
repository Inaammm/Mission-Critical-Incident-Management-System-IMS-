"""SQLAlchemy models for PostgreSQL (Source of Truth)"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Integer,
    Float,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class WorkItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Severity(str, enum.Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class ComponentType(str, enum.Enum):
    API = "API"
    MCP_HOST = "MCP_HOST"
    CACHE = "CACHE"
    QUEUE = "QUEUE"
    RDBMS = "RDBMS"
    NOSQL = "NOSQL"


class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    component_id = Column(String(255), nullable=False, index=True)
    component_type = Column(SAEnum(ComponentType), nullable=False)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    severity = Column(SAEnum(Severity), nullable=False)
    status = Column(SAEnum(WorkItemStatus), nullable=False, default=WorkItemStatus.OPEN)
    assigned_to = Column(String(255))
    signal_count = Column(Integer, default=1)
    first_signal_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime)
    closed_at = Column(DateTime)
    mttr_seconds = Column(Float)
    sla_deadline = Column(DateTime)

    rca = relationship("RCA", back_populates="work_item", uselist=False)
    audit_logs = relationship(
        "AuditLog", back_populates="work_item", order_by="AuditLog.created_at"
    )


class RCA(Base):
    __tablename__ = "rcas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id = Column(
        UUID(as_uuid=True), ForeignKey("work_items.id"), nullable=False, unique=True
    )
    incident_start = Column(DateTime, nullable=False)
    incident_end = Column(DateTime, nullable=False)
    root_cause_category = Column(String(255), nullable=False)
    root_cause_description = Column(Text, nullable=False)
    fix_applied = Column(Text, nullable=False)
    prevention_steps = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255))

    work_item = relationship("WorkItem", back_populates="rca")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    work_item_id = Column(
        UUID(as_uuid=True), ForeignKey("work_items.id"), nullable=False
    )
    action = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    performed_by = Column(String(255), default="system")
    created_at = Column(DateTime, default=datetime.utcnow)

    work_item = relationship("WorkItem", back_populates="audit_logs")


# TimescaleDB hypertable for signal aggregations
class SignalMetric(Base):
    __tablename__ = "signal_metrics"

    time = Column(DateTime, primary_key=True)
    component_id = Column(String(255), primary_key=True)
    component_type = Column(String(50))
    signal_count = Column(Integer, default=0)
    avg_latency_ms = Column(Float)
