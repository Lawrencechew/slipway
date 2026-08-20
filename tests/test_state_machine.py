from app.state_machine import can_transition
from app.models import PlanStatus


def test_allowed_transitions():
    assert can_transition(PlanStatus.DRAFT, PlanStatus.VALIDATING)
    assert can_transition(PlanStatus.VALIDATING, PlanStatus.READY)
    assert can_transition(PlanStatus.READY, PlanStatus.APPROVED)
    assert can_transition(PlanStatus.APPROVED, PlanStatus.APPLIED)


def test_disallowed_transitions():
    assert not can_transition(PlanStatus.INVALID, PlanStatus.APPROVED)
    assert not can_transition(PlanStatus.APPLIED, PlanStatus.READY)
