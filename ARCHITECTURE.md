# Architecture Document

## System Design Decisions

### 1. Why Redis Streams (not Kafka/RabbitMQ)?

For this scale (10k signals/sec), Redis Streams provides:
- Sub-millisecond latency
- Built-in consumer groups for horizontal scaling
- Already in-stack (used for cache and pub/sub)
- No additional infrastructure complexity
- Automatic backpressure via stream length limits (`MAXLEN`)

If the system needed to scale to 1M+ signals/sec across multiple data centers, Kafka would be the right choice.

### 2. Data Store Separation

| Store | Data | Why |
|-------|------|-----|
| PostgreSQL (TimescaleDB) | Work items, RCA, audit logs, time-series aggregations | ACID transactions for state integrity; time-series extension for signal metrics |
| MongoDB | Raw signal payloads | Schema-flexible, handles high write throughput, natural fit for JSON error payloads with varying structures |
| Redis | Stream buffer, debounce counters, dashboard cache, pub/sub | In-memory speed for hot-path operations; Redis Streams for reliable buffering |

### 3. Debouncing Strategy

The debouncing logic uses Redis atomic counters with TTL:

```
Signal arrives for CACHE_CLUSTER_01:
  1. INCR debounce:CACHE_CLUSTER_01  (atomic)
  2. If count == 1: set TTL to 10s, create work item immediately
  3. If 1 < count < 100: accumulate, link to existing work item
  4. If count == 100: threshold reached (logged for metrics)
  5. After TTL expires: counter resets, next signal creates new work item
```

This means the FIRST signal always creates a work item (for responsiveness), and subsequent signals are linked to it. The threshold (100) is used for metrics/alerting escalation, not for blocking.

### 4. Circuit Breaker Configuration

```python
mongo_breaker = CircuitBreaker(fail_max=5, reset_timeout=30)
postgres_breaker = CircuitBreaker(fail_max=5, reset_timeout=30)
```

- **OPEN state**: After 5 consecutive failures, stop calling the store
- **HALF-OPEN state**: After 30s, allow one test request
- **Key insight**: When MongoDB breaker opens, signals remain in Redis Streams. They are NOT lost. The consumer will retry them when the breaker closes.

### 5. Rate Limiting Implementation

Uses a sliding window counter in Redis (sorted set):
- Each request adds a timestamp to the sorted set
- Window is 1 second
- If count > threshold (10,000), return 429
- Old entries auto-expire

This is preferred over token-bucket for this use case because:
- More accurate at the boundary
- No burst exceeding the limit
- Simple Redis implementation

### 6. State Machine Design

```
OPEN ──────> INVESTIGATING ──────> RESOLVED ──────> CLOSED
              │       ▲               │       ▲
              └───────┘               └───────┘
              (re-open)             (re-investigate)
```

Each state is a class implementing:
- `allowed_transitions()`: What states can follow
- `validate_transition()`: Business rules (e.g., RCA check)
- `on_enter()`: Side effects (e.g., calculate MTTR)

### 7. Concurrency Model

- **FastAPI**: Async/await throughout (no thread blocking)
- **Consumer**: Single asyncio task consuming from Redis Stream with batch reads (200 messages per iteration)
- **Database writes**: Retry with exponential backoff (tenacity)
- **State transitions**: Optimistic concurrency via SQLAlchemy session

### 8. WebSocket Architecture

```
Redis Pub/Sub ──> Backend (subscriber) ──> WebSocket ──> React Client
```

When a work item is created or transitions state:
1. The change is committed to PostgreSQL
2. An event is published to Redis pub/sub channel
3. The WebSocket handler forwards to all connected clients
4. React app updates the UI without polling

### 9. SLA Breach Monitoring

- Each work item gets a `sla_deadline` based on severity
- Frontend shows countdown timer with color coding:
  - Green: > 15 min remaining
  - Yellow: < 15 min remaining  
  - Red (pulsing): < 5 min remaining
- The deadline is calculated at work item creation time

### 10. Observability Stack

```
FastAPI ──> /metrics (Prometheus format)
  │
  ├── ims_signals_ingested_total (Counter)
  ├── ims_work_items_created_total (Counter)
  ├── ims_state_transitions_total (Counter, labels: from_state, to_state)
  ├── ims_signals_per_second (Gauge)
  ├── ims_active_incidents (Gauge, labels: severity)
  └── ims_mttr_seconds (Histogram, buckets: 1m, 5m, 10m, 15m, 30m, 1h, 2h)
```

Console output every 5 seconds:
```
[METRICS] Throughput: 2450.3 signals/sec | Total ingested: 125000
```
