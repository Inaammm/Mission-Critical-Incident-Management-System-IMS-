"""Strategy Pattern for alerting based on component type and severity"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from app.models.database import ComponentType, Severity


@dataclass
class AlertPayload:
    component_id: str
    component_type: ComponentType
    severity: Severity
    title: str
    message: str
    channel: str  # e.g., "pager", "slack", "email", "dashboard"


class AlertStrategy(ABC):
    """Base strategy for alert routing"""

    @abstractmethod
    def determine_severity(self, component_type: ComponentType) -> Severity:
        pass

    @abstractmethod
    def get_alert_channels(self, severity: Severity) -> list[str]:
        pass

    def create_alert(
        self, component_id: str, component_type: ComponentType, error_message: str
    ) -> AlertPayload:
        severity = self.determine_severity(component_type)
        channels = self.get_alert_channels(severity)
        return AlertPayload(
            component_id=component_id,
            component_type=component_type,
            severity=severity,
            title=f"[{severity.value}] {component_type.value} failure: {component_id}",
            message=error_message,
            channel=channels[0] if channels else "dashboard",
        )


class DefaultAlertStrategy(AlertStrategy):
    """Default alerting: severity based on component criticality"""

    COMPONENT_SEVERITY_MAP = {
        ComponentType.RDBMS: Severity.P0,
        ComponentType.QUEUE: Severity.P0,
        ComponentType.API: Severity.P1,
        ComponentType.MCP_HOST: Severity.P1,
        ComponentType.CACHE: Severity.P2,
        ComponentType.NOSQL: Severity.P2,
    }

    SEVERITY_CHANNELS = {
        Severity.P0: ["pager", "slack", "dashboard"],
        Severity.P1: ["slack", "dashboard"],
        Severity.P2: ["dashboard"],
        Severity.P3: ["dashboard"],
    }

    def determine_severity(self, component_type: ComponentType) -> Severity:
        return self.COMPONENT_SEVERITY_MAP.get(component_type, Severity.P2)

    def get_alert_channels(self, severity: Severity) -> list[str]:
        return self.SEVERITY_CHANNELS.get(severity, ["dashboard"])


class AggressiveAlertStrategy(AlertStrategy):
    """Aggressive: everything is high priority (e.g., during an outage window)"""

    def determine_severity(self, component_type: ComponentType) -> Severity:
        if component_type in (ComponentType.RDBMS, ComponentType.QUEUE):
            return Severity.P0
        return Severity.P1

    def get_alert_channels(self, severity: Severity) -> list[str]:
        return ["pager", "slack", "dashboard"]


# Factory
_current_strategy: AlertStrategy = DefaultAlertStrategy()


def get_alert_strategy() -> AlertStrategy:
    return _current_strategy


def set_alert_strategy(strategy: AlertStrategy) -> None:
    global _current_strategy
    _current_strategy = strategy
