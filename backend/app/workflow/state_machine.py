"""State Pattern for Work Item lifecycle management"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING
from app.models.database import WorkItemStatus

if TYPE_CHECKING:
    from app.models.database import WorkItem


class WorkItemState(ABC):
    """Base state class for Work Item lifecycle"""

    @property
    @abstractmethod
    def status(self) -> WorkItemStatus:
        pass

    @abstractmethod
    def allowed_transitions(self) -> list[WorkItemStatus]:
        pass

    def can_transition_to(self, target: WorkItemStatus) -> bool:
        return target in self.allowed_transitions()

    @abstractmethod
    def validate_transition(
        self, work_item: "WorkItem", target: WorkItemStatus
    ) -> tuple[bool, str]:
        """Validate if transition is allowed. Returns (allowed, reason)."""
        pass

    def on_enter(self, work_item: "WorkItem") -> dict:
        """Hook called when entering this state. Returns extra fields to update."""
        return {}


class OpenState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.OPEN

    def allowed_transitions(self) -> list[WorkItemStatus]:
        return [WorkItemStatus.INVESTIGATING]

    def validate_transition(
        self, work_item, target: WorkItemStatus
    ) -> tuple[bool, str]:
        if target not in self.allowed_transitions():
            return (
                False,
                f"Cannot transition from OPEN to {target}. Must go to INVESTIGATING first.",
            )
        return True, ""


class InvestigatingState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.INVESTIGATING

    def allowed_transitions(self) -> list[WorkItemStatus]:
        return [WorkItemStatus.RESOLVED, WorkItemStatus.OPEN]

    def validate_transition(
        self, work_item, target: WorkItemStatus
    ) -> tuple[bool, str]:
        if target not in self.allowed_transitions():
            return False, f"Cannot transition from INVESTIGATING to {target}."
        return True, ""


class ResolvedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.RESOLVED

    def allowed_transitions(self) -> list[WorkItemStatus]:
        return [WorkItemStatus.CLOSED, WorkItemStatus.INVESTIGATING]

    def validate_transition(
        self, work_item, target: WorkItemStatus
    ) -> tuple[bool, str]:
        if target not in self.allowed_transitions():
            return False, f"Cannot transition from RESOLVED to {target}."
        if target == WorkItemStatus.CLOSED:
            # Mandatory RCA check
            if not work_item.rca:
                return (
                    False,
                    "Cannot close work item without a completed RCA. Please submit RCA first.",
                )
        return True, ""

    def on_enter(self, work_item) -> dict:
        return {"resolved_at": datetime.utcnow()}


class ClosedState(WorkItemState):
    @property
    def status(self) -> WorkItemStatus:
        return WorkItemStatus.CLOSED

    def allowed_transitions(self) -> list[WorkItemStatus]:
        return []  # Terminal state

    def validate_transition(
        self, work_item, target: WorkItemStatus
    ) -> tuple[bool, str]:
        return False, "Cannot transition from CLOSED state. This is a terminal state."

    def on_enter(self, work_item) -> dict:
        now = datetime.utcnow()
        mttr = None
        if work_item.first_signal_at:
            mttr = (now - work_item.first_signal_at).total_seconds()
        return {"closed_at": now, "mttr_seconds": mttr}


# State factory
STATE_MAP: dict[WorkItemStatus, WorkItemState] = {
    WorkItemStatus.OPEN: OpenState(),
    WorkItemStatus.INVESTIGATING: InvestigatingState(),
    WorkItemStatus.RESOLVED: ResolvedState(),
    WorkItemStatus.CLOSED: ClosedState(),
}


def get_state(status: WorkItemStatus) -> WorkItemState:
    return STATE_MAP[status]
