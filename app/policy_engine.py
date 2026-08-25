from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .schemas import ServiceSpec

POLICY_VERSION = "platform-policy-v1"


@dataclass
class PolicyDecisionEvaluation:
    outcome: str
    risk_level: str
    policy_version: str
    reasons: List[Dict[str, str]]
    required_approvals: List[str]
    blocking_violations: List[Dict[str, str]]
    advisory_warnings: List[Dict[str, str]]


def _reason(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


def evaluate_policy_decision(spec: ServiceSpec) -> PolicyDecisionEvaluation:
    payload = spec.spec or {}
    deployment = payload.get("deployment") or {}
    network = payload.get("network") or {}
    data = payload.get("data") or {}
    observability = payload.get("observability") or {}

    reasons: List[Dict[str, str]] = []
    required_approvals: List[str] = []
    blocking_violations: List[Dict[str, str]] = []
    advisory_warnings: List[Dict[str, str]] = []

    env = deployment.get("environment")
    if not env:
        blocking_violations.append(
            _reason(
                "MISSING_DEPLOYMENT_ENVIRONMENT",
                "deployment.environment is required for policy evaluation.",
            )
        )
    elif env not in {"dev", "development", "staging", "qa", "production"}:
        blocking_violations.append(
            _reason(
                "UNSUPPORTED_ENVIRONMENT",
                "deployment.environment must be one of dev/development/staging/qa/production.",
            )
        )

    is_production = env == "production"
    public_exposure = bool(network.get("public", False))
    sensitivity = str(data.get("sensitivity", "low")).lower()

    if sensitivity not in {"low", "medium", "high"}:
        blocking_violations.append(
            _reason(
                "INVALID_DATA_SENSITIVITY",
                "data.sensitivity must be one of low/medium/high when provided.",
            )
        )

    risk_score = 0

    if is_production:
        risk_score += 1
        reasons.append(
            _reason("PROD_ENVIRONMENT", "Production environment increases operational risk.")
        )
    if public_exposure:
        risk_score += 1
        reasons.append(
            _reason("PUBLIC_EXPOSURE", "Public exposure increases security and abuse risk.")
        )
    if sensitivity == "high":
        risk_score += 1
        reasons.append(
            _reason(
                "HIGH_DATA_SENSITIVITY",
                "High data sensitivity requires stronger governance and review.",
            )
        )
    elif sensitivity == "medium":
        reasons.append(
            _reason(
                "MEDIUM_DATA_SENSITIVITY",
                "Medium data sensitivity requires careful operational handling.",
            )
        )

    if is_production and public_exposure and sensitivity == "high":
        blocking_violations.append(
            _reason(
                "DISALLOWED_PROD_PUBLIC_HIGH_SENSITIVITY",
                "Production + public exposure + high data sensitivity is disallowed.",
            )
        )

    if not observability.get("metrics", False):
        advisory_warnings.append(
            _reason(
                "METRICS_NOT_ENABLED",
                "Metrics are disabled; observability may be insufficient for production incidents.",
            )
        )

    if blocking_violations:
        return PolicyDecisionEvaluation(
            outcome="BLOCKED",
            risk_level="HIGH",
            policy_version=POLICY_VERSION,
            reasons=reasons,
            required_approvals=[],
            blocking_violations=blocking_violations,
            advisory_warnings=advisory_warnings,
        )

    if risk_score == 0:
        risk_level = "LOW"
        outcome = "PASS"
        required_approvals = ["STANDARD_APPROVAL"]
    elif risk_score == 1:
        risk_level = "MEDIUM"
        outcome = "REQUIRES_APPROVAL"
        required_approvals = ["PLATFORM_OWNER_APPROVAL"]
    else:
        risk_level = "HIGH"
        outcome = "REQUIRES_APPROVAL"
        required_approvals = ["PLATFORM_OWNER_APPROVAL", "SECURITY_REVIEW_APPROVAL"]

    return PolicyDecisionEvaluation(
        outcome=outcome,
        risk_level=risk_level,
        policy_version=POLICY_VERSION,
        reasons=reasons,
        required_approvals=required_approvals,
        blocking_violations=[],
        advisory_warnings=advisory_warnings,
    )
