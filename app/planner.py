import datetime
import hashlib
import json
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import (
    DecisionOutcome,
    Plan as PlanModel,
    PlanStatus,
    PolicyDecision as PolicyDecisionModel,
    PolicyResult as PolicyResultModel,
    RiskLevel,
    Service,
    ServiceRevision,
)
from .policies import evaluate_policies
from .policy_engine import evaluate_policy_decision
from .schemas import Plan, PolicyDecisionSummary, ServiceSpec


def fingerprint_spec(spec: ServiceSpec) -> str:
    canonical = spec.dict_canonical()
    data = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def generate_artifacts(spec: ServiceSpec) -> List[Dict[str, Any]]:
    name = spec.metadata.name
    artifacts = []
    runtime_ver = spec.spec.get("runtime", {}).get("version", "3.13")

    dockerfile = (
        f"FROM python:{runtime_ver}\nWORKDIR /app\nCOPY . /app\n"
        'CMD ["python", "-m", "uvicorn", "app.main:app"]\n'
    )
    artifacts.append(
        {
            "path": f"{name}/Dockerfile",
            "action": "CREATE",
            "content": dockerfile,
            "reason": "runtime image and entrypoint",
        }
    )

    values = {
        "replicaCount": spec.spec.get("deployment", {}).get("replicas", 1),
        "resources": spec.spec.get("resources", {}),
    }
    artifacts.append(
        {
            "path": f"{name}/values.yaml",
            "action": "CREATE",
            "content": json.dumps(values, sort_keys=True, indent=2),
            "reason": "helm values for deployment",
        }
    )

    deployment = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name},
        "spec": {
            "replicas": spec.spec.get("deployment", {}).get("replicas", 1),
            "template": {"spec": {"containers": spec.spec.get("containers", [])}},
        },
    }
    artifacts.append(
        {
            "path": f"{name}/k8s/deployment.yaml",
            "action": "CREATE",
            "content": json.dumps(deployment, sort_keys=True, indent=2),
            "reason": "kubernetes deployment manifest",
        }
    )

    sa = {"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": f"{name}-sa"}}
    artifacts.append(
        {
            "path": f"{name}/k8s/serviceaccount.yaml",
            "action": "CREATE",
            "content": json.dumps(sa, sort_keys=True, indent=2),
            "reason": "service account for workload identity",
        }
    )

    if spec.spec.get("podDisruptionBudget") or spec.spec.get("deployment", {}).get(
        "environment"
    ) == "production":
        pdb = {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {"name": f"{name}-pdb"},
        }
        artifacts.append(
            {
                "path": f"{name}/k8s/pdb.yaml",
                "action": "CREATE",
                "content": json.dumps(pdb, sort_keys=True, indent=2),
                "reason": "pod disruption budget for availability",
            }
        )

    return artifacts


def decision_model_to_summary(decision: PolicyDecisionModel) -> PolicyDecisionSummary:
    return PolicyDecisionSummary(
        decision_id=decision.decision_id,
        outcome=decision.outcome.value,
        risk_level=decision.risk_level.value,
        policy_version=decision.policy_version,
        reasons=json.loads(decision.reasons or "[]"),
        required_approvals=json.loads(decision.required_approvals or "[]"),
        blocking_violations=json.loads(decision.blocking_violations or "[]"),
        advisory_warnings=json.loads(decision.advisory_warnings or "[]"),
        evaluated_at=decision.evaluated_at.isoformat() if decision.evaluated_at else None,
        is_stale=decision.is_stale,
        stale_reason=decision.stale_reason,
    )


def invalidate_active_decisions_for_service(
    db: Session, service_id: int, current_fingerprint: str, stale_reason: str
) -> int:
    decisions = (
        db.query(PolicyDecisionModel)
        .join(PlanModel, PlanModel.id == PolicyDecisionModel.plan_id)
        .join(ServiceRevision, ServiceRevision.id == PlanModel.service_revision_id)
        .filter(
            ServiceRevision.service_id == service_id,
            PolicyDecisionModel.is_stale.is_(False),
            PolicyDecisionModel.spec_fingerprint != current_fingerprint,
        )
        .all()
    )

    for decision in decisions:
        decision.is_stale = True
        decision.stale_reason = stale_reason
        db.add(decision)

    return len(decisions)


def create_plan(spec: ServiceSpec) -> Plan:
    fingerprint = fingerprint_spec(spec)
    policy_results = evaluate_policies(spec)
    decision = evaluate_policy_decision(spec)
    artifacts = generate_artifacts(spec)
    now = datetime.datetime.utcnow()
    plan_id = hashlib.sha1(f"{fingerprint}:{now.timestamp()}".encode("utf-8")).hexdigest()
    has_policy_failures = any(p.status == "FAIL" for p in policy_results)
    status = (
        "INVALID"
        if has_policy_failures or decision.outcome == "BLOCKED"
        else "READY"
    )

    db: Session = SessionLocal()
    decision_summary: PolicyDecisionSummary
    try:
        svc_name = spec.metadata.name
        svc = db.query(Service).filter(Service.name == svc_name).first()
        if not svc:
            svc = Service(name=svc_name, owner=spec.metadata.owner, description=spec.metadata.description)
            db.add(svc)
            db.flush()

        rev = (
            db.query(ServiceRevision)
            .filter(ServiceRevision.service_id == svc.id)
            .order_by(ServiceRevision.revision.desc())
            .first()
        )
        next_rev = 1 if not rev else rev.revision + 1
        spec_text = json.dumps(spec.dict_canonical(), sort_keys=True)
        svc_rev = ServiceRevision(
            service_id=svc.id, revision=next_rev, spec=spec_text, fingerprint=fingerprint
        )
        db.add(svc_rev)
        db.flush()

        plan_model = PlanModel(
            id=plan_id,
            service_revision_id=svc_rev.id,
            spec_fingerprint=fingerprint,
            status=getattr(PlanStatus, status),
            artifacts=json.dumps(artifacts, sort_keys=True),
        )
        db.add(plan_model)
        db.flush()

        decision_id = hashlib.sha1(
            f"{plan_id}:{decision.policy_version}:{fingerprint}".encode("utf-8")
        ).hexdigest()
        decision_model = PolicyDecisionModel(
            decision_id=decision_id,
            plan_id=plan_id,
            spec_fingerprint=fingerprint,
            outcome=getattr(DecisionOutcome, decision.outcome),
            risk_level=getattr(RiskLevel, decision.risk_level),
            policy_version=decision.policy_version,
            reasons=json.dumps(decision.reasons, sort_keys=True),
            required_approvals=json.dumps(decision.required_approvals, sort_keys=True),
            blocking_violations=json.dumps(decision.blocking_violations, sort_keys=True),
            advisory_warnings=json.dumps(decision.advisory_warnings, sort_keys=True),
            is_stale=False,
            stale_reason=None,
        )
        db.add(decision_model)

        prev_plans = (
            db.query(PlanModel)
            .join(ServiceRevision, ServiceRevision.id == PlanModel.service_revision_id)
            .filter(ServiceRevision.service_id == svc.id, PlanModel.id != plan_id)
            .all()
        )
        for prev_plan in prev_plans:
            prev_plan.status = PlanStatus.SUPERSEDED
            db.add(prev_plan)

        invalidate_active_decisions_for_service(
            db=db,
            service_id=svc.id,
            current_fingerprint=fingerprint,
            stale_reason="NEWER_PLAN_CREATED",
        )

        for pr in policy_results:
            db.add(
                PolicyResultModel(
                    plan_id=plan_id,
                    policy=pr.policy,
                    status=pr.status,
                    severity=pr.severity,
                    explanation=pr.explanation,
                    remediation=pr.remediation,
                )
            )

        db.commit()
        db.refresh(decision_model)
        decision_summary = decision_model_to_summary(decision_model)
    finally:
        db.close()

    return Plan(
        id=plan_id,
        spec_fingerprint=fingerprint,
        created=now.isoformat() + "Z",
        status=status,
        policy_results=policy_results,
        policy_decision=decision_summary,
        artifacts=artifacts,
    )


def persist_revision(db: Session, svc: Service, spec: ServiceSpec, fingerprint: str):
    rev = (
        db.query(ServiceRevision)
        .filter(ServiceRevision.service_id == svc.id)
        .order_by(ServiceRevision.revision.desc())
        .first()
    )
    next_rev = 1 if not rev else rev.revision + 1
    spec_text = json.dumps(spec.dict_canonical(), sort_keys=True)
    svc_rev = ServiceRevision(service_id=svc.id, revision=next_rev, spec=spec_text, fingerprint=fingerprint)
    db.add(svc_rev)
    db.flush()
    return svc_rev
