from app.policy_engine import POLICY_VERSION, evaluate_policy_decision
from app.schemas import Metadata, ServiceSpec


def make_spec(
    *,
    env: str = "staging",
    public: bool = False,
    sensitivity: str = "low",
    metrics: bool = True,
):
    return ServiceSpec(
        metadata=Metadata(name="decision-svc", owner="platform"),
        spec={
            "deployment": {"environment": env, "replicas": 2},
            "network": {"public": public},
            "data": {"sensitivity": sensitivity},
            "resources": {"limits": {"cpu": "250m"}},
            "containers": [
                {
                    "name": "app",
                    "securityContext": {"runAsNonRoot": True},
                    "readinessProbe": {"httpGet": {"path": "/health"}},
                    "livenessProbe": {"httpGet": {"path": "/health"}},
                }
            ],
            "observability": {"metrics": metrics},
        },
    )


def test_low_risk_decision_pass():
    decision = evaluate_policy_decision(make_spec(env="staging", public=False, sensitivity="low"))
    assert decision.risk_level == "LOW"
    assert decision.outcome == "PASS"
    assert decision.required_approvals == ["STANDARD_APPROVAL"]


def test_production_increases_risk_and_requires_approval():
    decision = evaluate_policy_decision(make_spec(env="production", public=False, sensitivity="low"))
    assert decision.risk_level == "MEDIUM"
    assert decision.outcome == "REQUIRES_APPROVAL"
    assert "PLATFORM_OWNER_APPROVAL" in decision.required_approvals


def test_public_exposure_increases_risk():
    decision = evaluate_policy_decision(make_spec(env="staging", public=True, sensitivity="low"))
    assert decision.risk_level == "MEDIUM"
    assert any(reason["code"] == "PUBLIC_EXPOSURE" for reason in decision.reasons)


def test_high_risk_combination_requires_stronger_approval():
    decision = evaluate_policy_decision(make_spec(env="production", public=True, sensitivity="low"))
    assert decision.risk_level == "HIGH"
    assert decision.outcome == "REQUIRES_APPROVAL"
    assert decision.required_approvals == [
        "PLATFORM_OWNER_APPROVAL",
        "SECURITY_REVIEW_APPROVAL",
    ]


def test_disallowed_combination_is_blocked():
    decision = evaluate_policy_decision(
        make_spec(env="production", public=True, sensitivity="high")
    )
    assert decision.outcome == "BLOCKED"
    assert any(
        item["code"] == "DISALLOWED_PROD_PUBLIC_HIGH_SENSITIVITY"
        for item in decision.blocking_violations
    )


def test_policy_version_and_reasons_present():
    decision = evaluate_policy_decision(make_spec(env="production", public=False, sensitivity="medium"))
    assert decision.policy_version == POLICY_VERSION
    assert len(decision.reasons) > 0


def test_repeated_evaluation_is_equivalent_for_unchanged_input():
    spec = make_spec(env="production", public=True, sensitivity="low")
    decision_a = evaluate_policy_decision(spec)
    decision_b = evaluate_policy_decision(spec)
    assert decision_a.__dict__ == decision_b.__dict__
