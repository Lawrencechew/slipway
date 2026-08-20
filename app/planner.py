import hashlib
import json
import datetime
from typing import Dict, Any
from .schemas import ServiceSpec, Plan, PolicyResult
from .policies import evaluate_policies


def fingerprint_spec(spec: ServiceSpec) -> str:
    canonical = spec.dict_canonical()
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def generate_artifacts(spec: ServiceSpec) -> Dict[str, str]:
    # Deterministic small artifact generation for v1
    name = spec.metadata.name
    artifacts = {}
    # Dockerfile
    dockerfile = f"FROM python:{spec.spec.get('runtime', {}).get('version','3.13')}\nWORKDIR /app\nCOPY . /app\nCMD [\"python\", \"-m\", \"uvicorn\", \"app.main:app\"]\n"
    artifacts[f"{name}/Dockerfile"] = dockerfile

    # helm values
    values = {
        "replicaCount": spec.spec.get("deployment", {}).get("replicas", 1),
        "resources": spec.spec.get("resources", {}),
    }
    artifacts[f"{name}/values.yaml"] = json.dumps(values, indent=2)

    return artifacts


def create_plan(spec: ServiceSpec) -> Plan:
    fingerprint = fingerprint_spec(spec)
    policy_results = evaluate_policies(spec)
    artifacts = generate_artifacts(spec)
    plan_id = hashlib.sha1((fingerprint + str(datetime.datetime.utcnow().timestamp())).encode("utf-8")).hexdigest()
    plan = Plan(
        id=plan_id,
        spec_fingerprint=fingerprint,
        created=datetime.datetime.utcnow().isoformat() + "Z",
        status="READY" if all(p.status == "PASS" or p.status == "WARN" for p in policy_results) else "INVALID",
        policy_results=policy_results,
        artifacts=artifacts,
    )
    return plan
