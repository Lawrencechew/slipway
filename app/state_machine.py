from typing import Dict
from .models import PlanStatus

# Allowed transitions mapping
ALLOWED: Dict[PlanStatus, set] = {
    PlanStatus.DRAFT: {PlanStatus.VALIDATING, PlanStatus.INVALID},
    PlanStatus.VALIDATING: {PlanStatus.READY, PlanStatus.INVALID},
    PlanStatus.INVALID: set(),
    PlanStatus.READY: {PlanStatus.APPROVED, PlanStatus.SUPERSEDED, PlanStatus.FAILED},
    PlanStatus.APPROVED: {PlanStatus.APPLIED, PlanStatus.SUPERSEDED},
    PlanStatus.APPLIED: {PlanStatus.SUPERSEDED},
    PlanStatus.FAILED: {PlanStatus.SUPERSEDED},
    PlanStatus.SUPERSEDED: set(),
}


def can_transition(from_state: PlanStatus, to_state: PlanStatus) -> bool:
    return to_state in ALLOWED.get(from_state, set())
