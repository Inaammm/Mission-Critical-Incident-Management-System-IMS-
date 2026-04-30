# Prompts, Specifications & Plans

## Initial Specification

The project was built from the "Engineering Challenge: Mission-Critical Incident Management System (IMS)" which required:

1. A resilient IMS to monitor a distributed stack (APIs, MCP Hosts, Distributed Caches, Async Queues, RDBMS, NoSQL stores)
2. High-volume signal ingestion (10k signals/sec) with debouncing
3. Workflow-driven UI with mandatory RCA before closure
4. Strategy Pattern for alerting, State Pattern for lifecycle management

## Architecture Plan

### Phase 1: Infrastructure Design
- **Decision**: Docker Compose with 7 services
- **Rationale**: TimescaleDB for time-series aggregations, MongoDB for high-volume raw signal storage (flexible schema), Redis for hot-path caching + stream-based message queue, Prometheus + Grafana for observability

### Phase 2: Backend Design
- **Framework**: FastAPI (Python 3.11) — chosen for native async support, automatic OpenAPI docs, Pydantic validation
- **Ingestion**: Redis Streams as buffer between ingestion API and processing consumer (backpressure handling)
- **Debouncing**: Redis atomic counters with TTL per component_id; threshold-based work item creation
- **Circuit Breaker**: Protects against cascading failures when MongoDB or PostgreSQL is slow
- **State Machine**: State Pattern with OpenState, InvestigatingState, ResolvedState, ClosedState classes
- **Alert Strategy**: Strategy Pattern with DefaultAlertStrategy (severity-based) and AggressiveAlertStrategy (all P0)

### Phase 3: Frontend Design
- **Stack**: React + TypeScript + Vite
- **Components**: IncidentList (live feed), IncidentDetail (signals + audit), RCAForm (mandatory fields), SLATimer (countdown)
- **Real-time**: WebSocket subscription for live incident updates
- **Deployment**: Multi-stage Docker build with nginx serving static assets + reverse proxy to backend

### Phase 4: Resilience
- Rate limiting via Redis sorted set (sliding window)
- Retry logic via tenacity library on MongoDB writes
- Circuit breaker on external store calls
- Redis Stream MAXLEN for backpressure (won't OOM if consumers are slow)
- Consumer group pattern for horizontal scaling

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Redis Streams over Kafka | Simpler deployment, sufficient for 10k/sec, built-in consumer groups |
| MongoDB for raw signals | Schema flexibility, horizontal scaling, good for append-heavy workloads |
| TimescaleDB over plain PostgreSQL | Native time-series aggregation functions, hypertables for signal_metrics |
| State Pattern over if/else | Extensible, testable, enforces valid transitions at compile-time |
| Strategy Pattern for alerts | Swappable alerting logic without modifying core workflow |
| Nginx reverse proxy | Single entry point, avoids CORS complexity, WebSocket upgrade support |

## Prompts Used

The system was built iteratively using the following high-level prompts:

1. "Build a Mission-Critical Incident Management System that ingests high-volume error signals from distributed infrastructure, debounces them into work items, manages incident lifecycle workflows, and provides a real-time dashboard"
2. "Include Circuit Breaker, SLA Breach Countdown, Audit Trail, Bulk Simulator, Prometheus Metrics"
3. "Use State Pattern for workflow and Strategy Pattern for alerting"
4. "Support 10k signals/sec ingestion, debouncing (100 signals/10s → 1 work item), mandatory RCA before closing, MTTR calculation, rate limiting, /health endpoint, throughput metrics every 5s"
5. "Docker Compose with PostgreSQL (TimescaleDB), MongoDB, Redis, Prometheus, Grafana"
6. "React + TypeScript + Vite frontend with IncidentList, IncidentDetail, RCAForm, SLATimer, WebSocket hook"

## Testing Plan

- Unit tests: State machine transitions, Strategy pattern alert generation, RCA validation (mandatory fields, blocks closure)
- Integration: Docker Compose full stack, simulate burst → verify debouncing → verify incident creation
- Manual E2E: Full lifecycle OPEN → INVESTIGATING → RESOLVED → (submit RCA) → CLOSED
