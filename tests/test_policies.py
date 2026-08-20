from app.schemas import ServiceSpec, Metadata
from app.policies import evaluate_policies


def make_spec(prod=False, replicas=2, limits=True, nonroot=True, privileged=False, pdb=True, metrics=True):
    spec = {
        "runtime": {"language": "python", "version": "3.13"},
        "deployment": {"environment": "production" if prod else "staging", "replicas": replicas},
        "resources": {"limits": {"cpu": "250m", "memory": "256Mi"}} if limits else {},
        "containers": [{"name": "app", "securityContext": {"runAsNonRoot": nonroot, "privileged": privileged}, "readinessProbe": {"httpGet": {"path": "/health"}} if nonroot else {}, "livenessProbe": {"httpGet": {"path": "/health"}} if nonroot else {}}],
        "podDisruptionBudget": {"minAvailable": 1} if pdb else None,
        "observability": {"metrics": metrics}
    }
    return ServiceSpec(metadata=Metadata(name="svc", owner="team"), spec=spec)


def test_production_replicas_policy_pass():
    s = make_spec(prod=True, replicas=3)
    res = evaluate_policies(s)
    assert any(r.policy == "production.replicas" and r.status == "PASS" for r in res)


def test_production_replicas_policy_fail():
    s = make_spec(prod=True, replicas=1)
    res = evaluate_policies(s)
    assert any(r.policy == "production.replicas" and r.status == "FAIL" for r in res)


def test_resource_limits_required():
    s = make_spec(prod=True, limits=False)
    res = evaluate_policies(s)
    assert any(r.policy == "production.resources.limits" and r.status == "FAIL" for r in res)


def test_non_root_and_privileged():
    s = make_spec(prod=True, nonroot=False, privileged=True)
    res = evaluate_policies(s)
    assert any(r.policy == "security.nonroot" and r.status == "FAIL" for r in res)
    assert any(r.policy == "security.no-privileged" and r.status == "FAIL" for r in res)


def test_probes_and_pdb():
    s = make_spec(prod=True, nonroot=True, pdb=False)
    res = evaluate_policies(s)
    assert any(r.policy == "production.readiness" and r.status == "PASS" for r in res)
    assert any(r.policy == "production.liveness" and r.status == "PASS" for r in res)
    assert any(r.policy == "production.pdb" and r.status == "FAIL" for r in res)


def test_observability_metrics():
    s = make_spec(prod=False, metrics=False)
    res = evaluate_policies(s)
    assert any(r.policy == "observability.metrics" for r in res)
