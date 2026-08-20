import hashlib
import json
import datetime
from typing import Dict, Any
from .schemas import ServiceSpec, Plan, PolicyResult
from .policies import evaluate_policies
from .db import SessionLocal, engine
from .models import Service, ServiceRevision, Plan as PlanModel, PolicyResult as PolicyResultModel
import json as _json
from sqlalchemy.orm import Session


def fingerprint_spec(spec: ServiceSpec) -> str:
    canonical = spec.dict_canonical()
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def generate_artifacts(spec: ServiceSpec):
    # Return structured deterministic artifacts: list of {path, action, content, reason}
    name = spec.metadata.name
    artifacts = []
    runtime_ver = spec.spec.get('runtime', {}).get('version', '3.13')

    dockerfile = f"FROM python:{runtime_ver}\nWORKDIR /app\nCOPY . /app\nCMD [\"python\", \"-m\", \"uvicorn\", \"app.main:app\"]\n"
    artifacts.append({
        "path": f"{name}/Dockerfile",
        "action": "CREATE",
        "content": dockerfile,
        "reason": "runtime image and entrypoint",
    })

    values = {
        "replicaCount": spec.spec.get("deployment", {}).get("replicas", 1),
        "resources": spec.spec.get("resources", {}),
    }
    artifacts.append({
        "path": f"{name}/values.yaml",
        "action": "CREATE",
        "content": json.dumps(values, sort_keys=True, indent=2),
        "reason": "helm values for deployment",
    })

    # Kubernetes Deployment (simplified and deterministic)
    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name},
        "spec": {
            "replicas": spec.spec.get("deployment", {}).get("replicas", 1),
            "template": {"spec": {"containers": spec.spec.get("containers", [])}}
        }
    }
    artifacts.append({
        "path": f"{name}/k8s/deployment.yaml",
        "action": "CREATE",
        "content": json.dumps(deployment, sort_keys=True, indent=2),
        "reason": "kubernetes deployment manifest",
    })

    # ServiceAccount and Workload Identity placeholder
    sa = {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": f"{name}-sa"}}
    artifacts.append({
        "path": f"{name}/k8s/serviceaccount.yaml",
        "action": "CREATE",
        "content": json.dumps(sa, sort_keys=True, indent=2),
        "reason": "service account for workload identity",
    })

    # PDB if requested
    if spec.spec.get('podDisruptionBudget') or spec.spec.get('deployment', {}).get('environment') == 'production':
        pdb = {"apiVersion": "policy/v1", "kind": "PodDisruptionBudget", "metadata": {"name": f"{name}-pdb"}}
        artifacts.append({
            "path": f"{name}/k8s/pdb.yaml",
            "action": "CREATE",
            "content": json.dumps(pdb, sort_keys=True, indent=2),
            "reason": "pod disruption budget for availability",
        })

    return artifacts


def create_plan(spec: ServiceSpec) -> Plan:
    fingerprint = fingerprint_spec(spec)
    policy_results = evaluate_policies(spec)
    artifacts = generate_artifacts(spec)
    plan_id = hashlib.sha1((fingerprint + str(datetime.datetime.utcnow().timestamp())).encode("utf-8")).hexdigest()
    status = "READY" if all(p.status == "PASS" or p.status == "WARN" for p in policy_results) else "INVALID"

    # persist plan and policy results to DB
    db: Session = SessionLocal()
    try:
        # Ensure service and revision exist or create minimal
        svc_name = spec.metadata.name
        svc = db.query(Service).filter(Service.name == svc_name).first()
        if not svc:
            svc = Service(name=svc_name, owner=spec.metadata.owner, description=spec.metadata.description)
            db.add(svc)
            db.flush()

        # determine revision number
        rev = db.query(ServiceRevision).filter(ServiceRevision.service_id == svc.id).order_by(ServiceRevision.revision.desc()).first()
        next_rev = 1 if not rev else rev.revision + 1
        spec_text = _json.dumps(spec.dict_canonical(), sort_keys=True)
        svc_rev = ServiceRevision(service_id=svc.id, revision=next_rev, spec=spec_text, fingerprint=fingerprint)
        db.add(svc_rev)
        db.flush()

        plan_model = PlanModel(id=plan_id, service_revision_id=svc_rev.id, spec_fingerprint=fingerprint)
        try:
            from .models import PlanStatus
            plan_model.status = getattr(PlanStatus, status)
        except Exception:
            plan_model.status = status
        plan_model.artifacts = _json.dumps(artifacts, sort_keys=True)
        # handle enum assignment

        db.add(plan_model)

        # supersede previous plans for this service
        prev_plans = db.query(PlanModel).join(ServiceRevision).filter(ServiceRevision.service_id == svc.id, PlanModel.id != plan_id).all()
        from .models import PlanStatus as _PS
        for pp in prev_plans:
            try:
                pp.status = _PS.SUPERSEDED
            except Exception:
                pp.status = "SUPERSEDED"
            db.add(pp)

        for pr in policy_results:
            pr_model = PolicyResultModel(plan_id=plan_id, policy=pr.policy, status=pr.status, severity=pr.severity, explanation=pr.explanation, remediation=pr.remediation)
            db.add(pr_model)

        db.commit()
    finally:
        db.close()

    plan = Plan(
        id=plan_id,
        spec_fingerprint=fingerprint,
        created=datetime.datetime.utcnow().isoformat() + "Z",
        status=status,
        policy_results=policy_results,
        artifacts=artifacts,
    )
    return plan


def persist_revision(db: Session, svc: Service, spec: ServiceSpec, fingerprint: str):
    # determine revision number
    rev = db.query(ServiceRevision).filter(ServiceRevision.service_id == svc.id).order_by(ServiceRevision.revision.desc()).first()
    next_rev = 1 if not rev else rev.revision + 1
    spec_text = _json.dumps(spec.dict_canonical(), sort_keys=True)
    svc_rev = ServiceRevision(service_id=svc.id, revision=next_rev, spec=spec_text, fingerprint=fingerprint)
    db.add(svc_rev)
    db.flush()
    return svc_rev
