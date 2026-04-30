# Incident Management System (IMS)

A mission-critical, high-throughput incident management system designed to monitor distributed infrastructure and manage failure mediation workflows.

## Quick Start

```bash
# Clone and start all services
docker-compose up --build

# Services will be available at:
# - Frontend Dashboard: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs (Swagger): http://localhost:8000/docs
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3001 (admin/admin)
```

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────────┐
│ Signal Sources  │────>│ FastAPI      │────>│ Redis Streams       │
│ (10k sig/sec)   │     │ (Rate Limited)│     │ (Backpressure Buffer)│
└─────────────────┘     └──────────────┘     └──────────┬──────────┘
                                                         │
                                              ┌──────────▼──────────┐
                                              │ Processing Consumer │
                                              │ - Debounce Logic    │
                                              │ - Circuit Breakers  │
                                              └─┬────────┬────────┬─┘
                                                │        │        │
                                    ┌───────────▼┐ ┌─────▼─────┐ ┌▼──────────┐
                                    │ PostgreSQL │ │  MongoDB  │ │   Redis   │
                                    │ (Src of    │ │ (Raw      │ │ (Cache +  │
                                    │  Truth)    │ │  Signals) │ │  Pub/Sub) │
                                    └────────────┘ └───────────┘ └─────┬─────┘
                                                                       │
                                                               ┌───────▼───────┐
                                                               │ React Dashboard│
                                                               │ (WebSocket)    │
                                                               └───────────────┘
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | Python 3.11 + FastAPI | Async API server |
| Source of Truth | PostgreSQL + TimescaleDB | Work items, RCA, audit trail, timeseries |
| Data Lake | MongoDB | Raw signal storage (audit log) |
| Cache/Buffer | Redis | Streams, pub/sub, debounce counters, dashboard cache |
| Frontend | React + TypeScript + Vite | Incident dashboard |
| Observability | Prometheus + Grafana | Metrics and dashboards |

## Key Features

### Core Requirements
- **High-throughput ingestion**: Handles 10,000+ signals/sec via Redis Streams buffer
- **Debouncing**: 100 signals for same component in 10s = 1 work item (configurable)
- **Workflow Engine**: OPEN -> INVESTIGATING -> RESOLVED -> CLOSED (State Pattern)
- **Mandatory RCA**: Cannot close an incident without complete Root Cause Analysis
- **MTTR Calculation**: Automatic Mean Time To Repair from first signal to RCA submission
- **Rate Limiting**: Token-bucket rate limiter on ingestion API
- **Alerting Strategy**: Strategy Pattern - P0 for RDBMS/Queue, P1 for API, P2 for Cache

### Extra Features
- **Circuit Breaker**: Protects against MongoDB/PostgreSQL failures (pybreaker)
- **SLA Countdown**: Per-severity SLA timers with visual countdown in UI
- **Audit Trail**: Every state change logged with who/when/what
- **Bulk Simulator**: Generate realistic signal bursts for demo/testing
- **Prometheus Metrics**: Full observability with pre-built Grafana dashboard

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/signals/` | Ingest single signal |
| POST | `/signals/batch` | Ingest batch of signals |
| GET | `/incidents` | List active incidents |
| GET | `/incidents/{id}` | Get incident details |
| GET | `/incidents/{id}/signals` | Get raw signals for incident |
| GET | `/incidents/{id}/audit` | Get audit trail |
| POST | `/incidents/{id}/transition` | Transition incident state |
| POST | `/incidents/{id}/rca` | Submit RCA |
| GET | `/incidents/{id}/rca` | Get RCA |
| GET | `/dashboard/stats` | Dashboard statistics |
| GET | `/health` | Health check |
| GET | `/metrics` | Prometheus metrics |
| POST | `/simulate/burst` | Simulate signal burst |
| POST | `/simulate/flood` | Simulate high-throughput flood |
| WS | `/ws/incidents` | WebSocket live feed |

## Design Patterns

### State Pattern (Workflow)
Each work item state (`OpenState`, `InvestigatingState`, `ResolvedState`, `ClosedState`) encapsulates:
- Allowed transitions
- Validation logic (e.g., RCA check before closing)
- On-enter effects (e.g., MTTR calculation on close)

### Strategy Pattern (Alerting)
- `DefaultAlertStrategy`: Severity based on component criticality
- `AggressiveAlertStrategy`: Everything elevated during outage windows
- Easily extensible with new strategies

### Circuit Breaker Pattern (Resilience)
- Wraps MongoDB and PostgreSQL calls
- Opens after 5 failures, resets after 30s
- Signals remain buffered in Redis Streams during breaker-open state

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest app/tests/ -v
```

## Configuration

Environment variables (see `backend/app/config.py`):

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_URL` | `postgresql+asyncpg://ims:ims_secret@localhost:5432/ims_db` | PostgreSQL connection |
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection |
| `RATE_LIMIT_SIGNALS_PER_SECOND` | `10000` | Rate limit threshold |
| `DEBOUNCE_WINDOW_SECONDS` | `10` | Debounce time window |
| `DEBOUNCE_THRESHOLD` | `100` | Signals before creating work item |
| `SLA_P0_MINUTES` | `15` | P0 SLA deadline |
| `SLA_P1_MINUTES` | `60` | P1 SLA deadline |
| `SLA_P2_MINUTES` | `240` | P2 SLA deadline |

## Project Structure

```
ims/
├── docker-compose.yml          # All 7 services
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app + lifespan
│   │   ├── config.py          # Settings
│   │   ├── ingestion/         # Signal ingestion API + rate limiter
│   │   ├── processing/        # Consumer: debounce + circuit breaker
│   │   ├── workflow/          # State machine + alert strategy
│   │   ├── models/            # SQLAlchemy + Pydantic schemas
│   │   ├── repositories/     # PG, Mongo, Redis access layers
│   │   ├── api/              # REST routes + WebSocket
│   │   ├── metrics/          # Prometheus + throughput printer
│   │   ├── simulator/        # Bulk signal generator
│   │   └── tests/            # Unit tests
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Main app with live feed
│   │   ├── components/       # IncidentList, IncidentDetail, RCAForm, SLATimer
│   │   └── services/         # API client + WebSocket hook
│   ├── Dockerfile
│   └── nginx.conf
├── grafana/                   # Pre-built dashboard
└── prometheus/                # Scrape config
```
