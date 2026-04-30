"""Unit tests for RCA validation and state machine"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from app.workflow.state_machine import (
    OpenState,
    InvestigatingState,
    ResolvedState,
    ClosedState,
    get_state,
    WorkItemStatus,
)
from app.workflow.alert_strategy import (
    DefaultAlertStrategy,
    AggressiveAlertStrategy,
    ComponentType,
    Severity,
)


# --- State Machine Tests ---


class TestOpenState:
    def setup_method(self):
        self.state = OpenState()

    def test_allowed_transitions(self):
        assert self.state.allowed_transitions() == [WorkItemStatus.INVESTIGATING]

    def test_can_transition_to_investigating(self):
        assert self.state.can_transition_to(WorkItemStatus.INVESTIGATING) is True

    def test_cannot_transition_to_resolved(self):
        assert self.state.can_transition_to(WorkItemStatus.RESOLVED) is False

    def test_cannot_transition_to_closed(self):
        assert self.state.can_transition_to(WorkItemStatus.CLOSED) is False

    def test_validate_valid_transition(self):
        work_item = MagicMock()
        allowed, reason = self.state.validate_transition(
            work_item, WorkItemStatus.INVESTIGATING
        )
        assert allowed is True
        assert reason == ""

    def test_validate_invalid_transition(self):
        work_item = MagicMock()
        allowed, reason = self.state.validate_transition(
            work_item, WorkItemStatus.CLOSED
        )
        assert allowed is False
        assert "OPEN" in reason


class TestInvestigatingState:
    def setup_method(self):
        self.state = InvestigatingState()

    def test_allowed_transitions(self):
        assert WorkItemStatus.RESOLVED in self.state.allowed_transitions()
        assert WorkItemStatus.OPEN in self.state.allowed_transitions()

    def test_cannot_skip_to_closed(self):
        work_item = MagicMock()
        allowed, _ = self.state.validate_transition(work_item, WorkItemStatus.CLOSED)
        assert allowed is False


class TestResolvedState:
    def setup_method(self):
        self.state = ResolvedState()

    def test_cannot_close_without_rca(self):
        work_item = MagicMock()
        work_item.rca = None
        allowed, reason = self.state.validate_transition(
            work_item, WorkItemStatus.CLOSED
        )
        assert allowed is False
        assert "RCA" in reason

    def test_can_close_with_rca(self):
        work_item = MagicMock()
        work_item.rca = MagicMock()  # RCA exists
        allowed, reason = self.state.validate_transition(
            work_item, WorkItemStatus.CLOSED
        )
        assert allowed is True

    def test_can_reopen_to_investigating(self):
        work_item = MagicMock()
        allowed, _ = self.state.validate_transition(
            work_item, WorkItemStatus.INVESTIGATING
        )
        assert allowed is True


class TestClosedState:
    def setup_method(self):
        self.state = ClosedState()

    def test_no_transitions_allowed(self):
        assert self.state.allowed_transitions() == []

    def test_cannot_transition(self):
        work_item = MagicMock()
        allowed, reason = self.state.validate_transition(work_item, WorkItemStatus.OPEN)
        assert allowed is False
        assert "terminal" in reason.lower()

    def test_on_enter_calculates_mttr(self):
        work_item = MagicMock()
        work_item.first_signal_at = datetime.utcnow() - timedelta(hours=1)
        result = self.state.on_enter(work_item)
        assert "closed_at" in result
        assert "mttr_seconds" in result
        assert result["mttr_seconds"] > 3500  # ~1 hour


# --- Alert Strategy Tests ---


class TestDefaultAlertStrategy:
    def setup_method(self):
        self.strategy = DefaultAlertStrategy()

    def test_rdbms_is_p0(self):
        assert self.strategy.determine_severity(ComponentType.RDBMS) == Severity.P0

    def test_cache_is_p2(self):
        assert self.strategy.determine_severity(ComponentType.CACHE) == Severity.P2

    def test_queue_is_p0(self):
        assert self.strategy.determine_severity(ComponentType.QUEUE) == Severity.P0

    def test_api_is_p1(self):
        assert self.strategy.determine_severity(ComponentType.API) == Severity.P1

    def test_p0_gets_pager(self):
        channels = self.strategy.get_alert_channels(Severity.P0)
        assert "pager" in channels

    def test_p2_only_dashboard(self):
        channels = self.strategy.get_alert_channels(Severity.P2)
        assert channels == ["dashboard"]

    def test_create_alert_returns_payload(self):
        alert = self.strategy.create_alert(
            "RDBMS_PRIMARY", ComponentType.RDBMS, "Connection lost"
        )
        assert alert.severity == Severity.P0
        assert "P0" in alert.title
        assert alert.component_id == "RDBMS_PRIMARY"


class TestAggressiveAlertStrategy:
    def setup_method(self):
        self.strategy = AggressiveAlertStrategy()

    def test_everything_high_priority(self):
        assert self.strategy.determine_severity(ComponentType.CACHE) == Severity.P1
        assert self.strategy.determine_severity(ComponentType.RDBMS) == Severity.P0

    def test_all_channels_active(self):
        channels = self.strategy.get_alert_channels(Severity.P1)
        assert "pager" in channels


# --- RCA Validation Tests ---


class TestRCAValidation:
    """Test that RCA completeness is enforced"""

    def test_mandatory_rca_blocks_closure(self):
        """Core requirement: cannot close without RCA"""
        state = ResolvedState()
        work_item = MagicMock()
        work_item.rca = None

        allowed, reason = state.validate_transition(work_item, WorkItemStatus.CLOSED)
        assert allowed is False
        assert "RCA" in reason

    def test_rca_allows_closure(self):
        """With RCA present, closure is allowed"""
        state = ResolvedState()
        work_item = MagicMock()
        work_item.rca = MagicMock()

        allowed, _ = state.validate_transition(work_item, WorkItemStatus.CLOSED)
        assert allowed is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
