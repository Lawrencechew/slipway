from app.schemas import ServiceSpec, Metadata
from app.planner import create_plan, fingerprint_spec


def sample_spec():
    return ServiceSpec(
        metadata=Metadata(name="orders-api", owner="commerce", description=""),
        spec={
            "runtime": {"language": "python", "version": "3.13"},
            "deployment": {"environment": "production", "replicas": 2},
            "resources": {"limits": {"cpu": "250m", "memory": "256Mi"}},
            "observability": {"metrics": True},
            "containers": [{"name": "app", "securityContext": {"runAsNonRoot": True}, "readinessProbe": {"httpGet": {"path": "/health"}}, "livenessProbe": {"httpGet": {"path": "/health"}} }],
            "podDisruptionBudget": {"minAvailable": 1},
        },
    )


def test_fingerprint_and_plan():
    spec = sample_spec()
    fp = fingerprint_spec(spec)
    assert isinstance(fp, str) and len(fp) == 64
    plan = create_plan(spec)
    assert plan.spec_fingerprint == fp
    assert plan.status == "READY"
    assert plan.policy_decision is not None
    assert plan.policy_decision.policy_version == "platform-policy-v1"
    assert plan.policy_decision.outcome in {"PASS", "REQUIRES_APPROVAL", "BLOCKED"}
    assert any(a.get('path') == 'orders-api/Dockerfile' for a in plan.artifacts)
