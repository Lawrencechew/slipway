from typing import List
from .schemas import ServiceSpec, PolicyResult


def evaluate_policies(spec: ServiceSpec) -> List[PolicyResult]:
    results = []
    meta = spec.metadata
    s = spec.spec

    # Production policy example
    env = s.get("deployment", {}).get("environment")
    if env == "production":
        replicas = s.get("deployment", {}).get("replicas", 1)
        if replicas >= 2:
            results.append(PolicyResult(policy="production.replicas", status="PASS", severity="medium", explanation="replica requirement met", remediation=None))
        else:
            results.append(PolicyResult(policy="production.replicas", status="FAIL", severity="high", explanation="replicas < 2 in production", remediation="Set replicas >= 2"))

        # resource limits required
        resources = s.get("resources", {})
        if resources.get("limits"):
            results.append(PolicyResult(policy="production.resources.limits", status="PASS", severity="medium", explanation="resource limits present", remediation=None))
        else:
            results.append(PolicyResult(policy="production.resources.limits", status="FAIL", severity="high", explanation="resource limits missing", remediation="Add resource limits"))

    # Security example
    containers = s.get("containers", [])
    for idx, c in enumerate(containers):
        if c.get("securityContext", {}).get("runAsNonRoot"):
            results.append(PolicyResult(policy="security.nonroot", status="PASS", severity="high", explanation=f"container {idx} non-root", remediation=None))
        else:
            results.append(PolicyResult(policy="security.nonroot", status="FAIL", severity="high", explanation=f"container {idx} may run as root", remediation="Set runAsNonRoot: true"))

    # Privileged prohibited
    for idx, c in enumerate(containers):
        if c.get("securityContext", {}).get("privileged"):
            results.append(PolicyResult(policy="security.no-privileged", status="FAIL", severity="critical", explanation=f"container {idx} privileged not allowed", remediation="Remove privileged: true"))
        else:
            results.append(PolicyResult(policy="security.no-privileged", status="PASS", severity="low", explanation=f"container {idx} not privileged", remediation=None))

    # Probes and PDB
    if s.get("deployment", {}).get("environment") == "production":
        for idx, c in enumerate(containers):
            if not c.get("readinessProbe"):
                results.append(PolicyResult(policy="production.readiness", status="FAIL", severity="high", explanation=f"container {idx} missing readinessProbe", remediation="Add readinessProbe"))
            else:
                results.append(PolicyResult(policy="production.readiness", status="PASS", severity="low", explanation=f"container {idx} has readinessProbe", remediation=None))
            if not c.get("livenessProbe"):
                results.append(PolicyResult(policy="production.liveness", status="FAIL", severity="high", explanation=f"container {idx} missing livenessProbe", remediation="Add livenessProbe"))
            else:
                results.append(PolicyResult(policy="production.liveness", status="PASS", severity="low", explanation=f"container {idx} has livenessProbe", remediation=None))

        # PodDisruptionBudget required
        if not s.get("podDisruptionBudget"):
            results.append(PolicyResult(policy="production.pdb", status="FAIL", severity="medium", explanation="PodDisruptionBudget required in production", remediation="Add PodDisruptionBudget"))
        else:
            results.append(PolicyResult(policy="production.pdb", status="PASS", severity="low", explanation="PDB present", remediation=None))

    # Observability
    if s.get("observability", {}).get("metrics"):
        results.append(PolicyResult(policy="observability.metrics", status="PASS", severity="low", explanation="metrics enabled", remediation=None))
    else:
        results.append(PolicyResult(policy="observability.metrics", status="WARN", severity="medium", explanation="metrics not enabled", remediation="Enable metrics in observable environments"))

    return results
