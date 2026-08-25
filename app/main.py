from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .schemas import ServiceSpec
from .planner import (
    create_plan,
    fingerprint_spec,
    invalidate_active_decisions_for_service,
    persist_revision,
)
from .db import get_db
from sqlalchemy.orm import Session
from . import models
from .auth import get_current_user, create_user
from typing import Dict
import json
import uvicorn

app = FastAPI(
    title="PavedPath",
    description="PavedPath converts a typed ServiceSpec into a policy-validated, deterministic Plan that can be reviewed, approved, audited and handed off to Git for CI/CD.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/users", status_code=201)
def users_create(body: Dict[str, str], db: Session = Depends(get_db)):
    username = body.get('username')
    display_name = body.get('display_name')
    if not username:
        raise HTTPException(status_code=400, detail="username required")
    existing = db.query(models.User).filter(models.User.username == username).first()
    if existing:
        return {"username": existing.username, "api_key": existing.api_key}
    user = create_user(db, username, display_name)
    db.commit()
    return {"username": user.username, "api_key": user.api_key}


@app.post("/specs", status_code=201)
def create_spec(
    spec: ServiceSpec,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # For v1 we keep specs in-memory or persist later
    # Validate basic fields
    if not spec.metadata.name:
        raise HTTPException(status_code=400, detail="metadata.name required")
    fp = fingerprint_spec(spec)
    # store minimal service and revision for spec
    svc = db.query(models.Service).filter(models.Service.name == spec.metadata.name).first()
    if not svc:
        svc = models.Service(name=spec.metadata.name, owner=spec.metadata.owner, description=spec.metadata.description)
        db.add(svc)
        db.flush()
    rev = persist_revision(db, svc, spec, fp)
    stale_count = invalidate_active_decisions_for_service(
        db=db,
        service_id=svc.id,
        current_fingerprint=fp,
        stale_reason="SERVICE_SPEC_UPDATED",
    )
    # audit
    ev = models.AuditEvent(event_type="SERVICE_SPEC_CREATED", actor=current_user.username, target=svc.name, detail=fp)
    db.add(ev)
    if stale_count:
        db.add(
            models.AuditEvent(
                event_type="POLICY_DECISIONS_STALE",
                actor=current_user.username,
                target=svc.name,
                detail=f"count={stale_count}",
            )
        )
    db.commit()
    return {"fingerprint": fp}


@app.post("/plans", status_code=201)
def plans_create(
    spec: ServiceSpec,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = create_plan(spec)
    ev = models.AuditEvent(
        event_type="PLAN_CREATED",
        actor=current_user.username,
        target=plan.id,
        detail=plan.spec_fingerprint,
    )
    db.add(ev)
    if plan.policy_decision:
        db.add(
            models.AuditEvent(
                event_type="POLICY_EVALUATED",
                actor=current_user.username,
                target=plan.id,
                detail=(
                    f"outcome={plan.policy_decision.outcome};"
                    f"risk={plan.policy_decision.risk_level};"
                    f"version={plan.policy_decision.policy_version}"
                ),
            )
        )
    db.commit()
    return plan.dict()


@app.post("/plans/{plan_id}/approve", status_code=200)
def approve_plan(
    plan_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")

    if plan.status != models.PlanStatus.READY:
        raise HTTPException(status_code=400, detail="only READY plans can be approved")

    decision = (
        db.query(models.PolicyDecision)
        .filter(models.PolicyDecision.plan_id == plan_id)
        .first()
    )
    if not decision:
        raise HTTPException(status_code=409, detail="policy decision missing; re-evaluate plan")
    if decision.is_stale:
        raise HTTPException(
            status_code=409,
            detail=f"policy decision is stale ({decision.stale_reason or 'unknown'}); re-evaluate plan",
        )
    if decision.outcome == models.DecisionOutcome.BLOCKED:
        raise HTTPException(status_code=400, detail="plan blocked by policy decision")

    service_id = plan.service_revision.service_id
    latest_revision = (
        db.query(models.ServiceRevision)
        .filter(models.ServiceRevision.service_id == service_id)
        .order_by(models.ServiceRevision.revision.desc())
        .first()
    )
    if latest_revision and latest_revision.fingerprint != plan.spec_fingerprint:
        decision.is_stale = True
        decision.stale_reason = "SERVICE_SPEC_UPDATED"
        db.add(decision)
        db.add(
            models.AuditEvent(
                event_type="PLAN_APPROVAL_REJECTED_STALE_POLICY",
                actor=current_user.username,
                target=plan.id,
                detail=plan.spec_fingerprint,
            )
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="plan decision stale after spec update; generate a new plan before approval",
        )

    existing = (
        db.query(models.Approval)
        .filter(
            models.Approval.plan_id == plan_id,
            models.Approval.approver_id == current_user.id,
        )
        .first()
    )
    if not existing:
        db.add(
            models.Approval(
                plan_id=plan_id,
                approver_id=current_user.id,
                plan_fingerprint=plan.spec_fingerprint,
            )
        )
        db.flush()

    required_approvals = json.loads(decision.required_approvals or "[]")
    required_count = max(1, len(required_approvals))
    approval_count = (
        db.query(models.Approval)
        .filter(models.Approval.plan_id == plan_id)
        .count()
    )

    approved_now = approval_count >= required_count
    if approved_now:
        plan.status = models.PlanStatus.APPROVED
        db.add(plan)
        db.add(
            models.AuditEvent(
                event_type="PLAN_APPROVED",
                actor=current_user.username,
                target=plan.id,
                detail=plan.spec_fingerprint,
            )
        )
    else:
        db.add(
            models.AuditEvent(
                event_type="PLAN_APPROVAL_RECORDED",
                actor=current_user.username,
                target=plan.id,
                detail=f"{approval_count}/{required_count}",
            )
        )

    db.commit()
    return {
        "approved": approved_now,
        "plan_id": plan_id,
        "required_approvals": required_approvals,
        "approval_count": approval_count,
        "required_approval_count": required_count,
        "outcome": decision.outcome.value,
        "risk_level": decision.risk_level.value,
    }


def run():
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
