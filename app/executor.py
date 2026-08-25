from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ExecutionResult:
    status: str
    summary: str
    error_info: str | None
    metadata: Dict[str, Any]


class LocalDeterministicExecutor:
    executor_type = "local-deterministic"
    executor_version = "v1"

    def execute(self, approved_plan_spec: Dict[str, Any]) -> ExecutionResult:
        simulate_failure = bool(
            approved_plan_spec.get("execution", {}).get("simulateFailure", False)
        )
        if simulate_failure:
            return ExecutionResult(
                status="FAILED",
                summary="Deterministic failure triggered by execution.simulateFailure.",
                error_info="SIMULATED_EXECUTION_FAILURE",
                metadata={"simulateFailure": True},
            )

        artifact_count = len(approved_plan_spec.get("containers", []))
        return ExecutionResult(
            status="SUCCEEDED",
            summary="Execution completed deterministically using approved plan input.",
            error_info=None,
            metadata={"containerCount": artifact_count},
        )
