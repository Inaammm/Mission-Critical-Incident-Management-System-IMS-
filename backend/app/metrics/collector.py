"""Metrics collection and Prometheus exposition"""

import time
import asyncio
from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class MetricsCollector:
    def __init__(self):
        self.start_time = time.time()
        self._signals_total = 0
        self._signals_window = []  # timestamps for signals/sec calc
        self._window_size = 5  # seconds

        # Prometheus metrics
        self.prom_signals_ingested = Counter(
            "ims_signals_ingested_total", "Total signals ingested"
        )
        self.prom_work_items_created = Counter(
            "ims_work_items_created_total", "Total work items created"
        )
        self.prom_state_transitions = Counter(
            "ims_state_transitions_total",
            "Total state transitions",
            ["from_state", "to_state"],
        )
        self.prom_signals_per_second = Gauge(
            "ims_signals_per_second", "Current signals per second throughput"
        )
        self.prom_active_incidents = Gauge(
            "ims_active_incidents", "Current active incidents", ["severity"]
        )
        self.prom_mttr = Histogram(
            "ims_mttr_seconds",
            "Mean Time To Repair distribution",
            buckets=[60, 300, 600, 900, 1800, 3600, 7200],
        )

    def record_signal_ingested(self):
        self._signals_total += 1
        self._signals_window.append(time.time())
        self.prom_signals_ingested.inc()

    def record_work_item_created(self):
        self.prom_work_items_created.inc()

    def record_state_transition(self, from_state: str, to_state: str):
        self.prom_state_transitions.labels(
            from_state=from_state, to_state=to_state
        ).inc()

    def record_mttr(self, seconds: float):
        self.prom_mttr.observe(seconds)

    def get_signals_per_second(self) -> float:
        now = time.time()
        cutoff = now - self._window_size
        self._signals_window = [t for t in self._signals_window if t > cutoff]
        rate = len(self._signals_window) / self._window_size
        self.prom_signals_per_second.set(rate)
        return rate

    @property
    def uptime_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def total_signals(self) -> int:
        return self._signals_total

    def get_prometheus_metrics(self) -> bytes:
        self.get_signals_per_second()  # update gauge
        return generate_latest()

    def get_content_type(self) -> str:
        return CONTENT_TYPE_LATEST


metrics_collector = MetricsCollector()


async def print_throughput_loop():
    """Background task: print throughput every 5 seconds"""
    while True:
        await asyncio.sleep(5)
        rate = metrics_collector.get_signals_per_second()
        total = metrics_collector.total_signals
        print(f"[METRICS] Throughput: {rate:.1f} signals/sec | Total ingested: {total}")
