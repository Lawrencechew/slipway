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
            "containers": [{"name": "app", "securityContext": {"runAsNonRoot": True}}],
        },
    )


def test_fingerprint_and_plan():
    spec = sample_spec()
    fp = fingerprint_spec(spec)
    assert isinstance(fp, str) and len(fp) == 64
    plan = create_plan(spec)
    assert plan.spec_fingerprint == fp
    assert plan.status == "READY"
    assert "orders-api/Dockerfile" in plan.artifacts
