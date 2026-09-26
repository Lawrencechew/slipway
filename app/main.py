import datetime
import hashlib
import json
from typing import Dict

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .auth import create_user, get_current_user
from .db import get_db
from .executor import LocalDeterministicExecutor
from .planner import (
    create_plan,
    fingerprint_spec,
    invalidate_active_decisions_for_service,
    persist_revision,
)
from .schemas import ExecutionRecord, ServiceSpec

app = FastAPI(
    title="Slipway",
    description=(
        "Slipway converts a typed ServiceSpec into a policy-validated, deterministic "
        "Plan that can be reviewed, approved, executed, and audited."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _parse_approval_list(decision: models.PolicyDecision) -> list[str]:
    try:
        values = json.loads(decision.required_approvals or "[]")
        return values if isinstance(values, list) else []
    except json.JSONDecodeError:
        return []


def _build_execution_record_payload(execution: models.Execution) -> ExecutionRecord:
    return ExecutionRecord(
        execution_id=execution.execution_id,
        plan_id=execution.plan_id,
        service_revision_id=execution.service_revision_id,
        policy_decision_id=execution.policy_decision_id,
        policy_version=execution.policy_version,
        approval_snapshot=json.loads(execution.approval_snapshot or "{}"),
        input_fingerprint=execution.input_fingerprint,
        status=execution.status.value,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        executor_type=execution.executor_type,
        executor_version=execution.executor_version,
        result_summary=execution.result_summary,
        error_info=execution.error_info,
        receipt=json.loads(execution.receipt or "{}"),
    )


def _assert_execution_eligible(
    db: Session, plan_id: str
) -> tuple[models.Plan, models.PolicyDecision, int, list[str]]:
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")

    if plan.status not in {models.PlanStatus.APPROVED, models.PlanStatus.APPLIED}:
        raise HTTPException(status_code=400, detail="plan is not approved for execution")

    decision = (
        db.query(models.PolicyDecision)
        .filter(models.PolicyDecision.plan_id == plan_id)
        .first()
    )
    if not decision:
        raise HTTPException(status_code=409, detail="no current policy decision for plan")
    if decision.is_stale:
        raise HTTPException(
            status_code=409,
            detail=f"policy decision is stale ({decision.stale_reason or 'unknown'})",
        )
    if decision.outcome == models.DecisionOutcome.BLOCKED:
        raise HTTPException(status_code=400, detail="blocked policy decisions cannot execute")

    if decision.spec_fingerprint != plan.spec_fingerprint:
        raise HTTPException(
            status_code=409,
            detail="policy decision fingerprint does not match approved plan fingerprint",
        )

    latest_revision = (
        db.query(models.ServiceRevision)
        .filter(models.ServiceRevision.service_id == plan.service_revision.service_id)
        .order_by(models.ServiceRevision.revision.desc())
        .first()
    )
    if latest_revision and latest_revision.fingerprint != plan.spec_fingerprint:
        decision.is_stale = True
        decision.stale_reason = "SERVICE_SPEC_UPDATED"
        db.add(decision)
        raise HTTPException(
            status_code=409,
            detail="service specification changed after approval; execution requires a new plan",
        )

    approvals = (
        db.query(models.Approval)
        .filter(
            models.Approval.plan_id == plan_id,
            models.Approval.plan_fingerprint == plan.spec_fingerprint,
        )
        .all()
    )
    if not approvals:
        raise HTTPException(status_code=400, detail="no fingerprint-bound approval for this plan")

    required_approvals = _parse_approval_list(decision)
    required_count = max(1, len(required_approvals))
    if len(approvals) < required_count:
        raise HTTPException(
            status_code=400,
            detail=f"insufficient approvals for execution ({len(approvals)}/{required_count})",
        )

    return plan, decision, required_count, required_approvals


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/users", status_code=201)
def users_create(body: Dict[str, str], db: Session = Depends(get_db)):
    username = body.get("username")
    display_name = body.get("display_name")
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
    if not spec.metadata.name:
        raise HTTPException(status_code=400, detail="metadata.name required")

    fp = fingerprint_spec(spec)
    svc = db.query(models.Service).filter(models.Service.name == spec.metadata.name).first()
    if not svc:
        svc = models.Service(
            name=spec.metadata.name,
            owner=spec.metadata.owner,
            description=spec.metadata.description,
        )
        db.add(svc)
        db.flush()
    persist_revision(db, svc, spec, fp)
    stale_count = invalidate_active_decisions_for_service(
        db=db,
        service_id=svc.id,
        current_fingerprint=fp,
        stale_reason="SERVICE_SPEC_UPDATED",
    )
    db.add(
        models.AuditEvent(
            event_type="SERVICE_SPEC_CREATED",
            actor=current_user.username,
            target=svc.name,
            detail=fp,
        )
    )
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
    db.add(
        models.AuditEvent(
            event_type="PLAN_CREATED",
            actor=current_user.username,
            target=plan.id,
            detail=plan.spec_fingerprint,
        )
    )
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

    latest_revision = (
        db.query(models.ServiceRevision)
        .filter(models.ServiceRevision.service_id == plan.service_revision.service_id)
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

    required_approvals = _parse_approval_list(decision)
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


@app.post("/plans/{plan_id}/execute", response_model=ExecutionRecord)
def execute_plan(
    plan_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    plan, decision, _, _ = _assert_execution_eligible(db, plan_id)

    execution_key = hashlib.sha256(
        f"{plan.id}:{plan.spec_fingerprint}:{decision.decision_id}:{decision.policy_version}".encode(
            "utf-8"
        )
    ).hexdigest()
    existing_execution = (
        db.query(models.Execution)
        .filter(models.Execution.execution_key == execution_key)
        .first()
    )
    if existing_execution:
        return _build_execution_record_payload(existing_execution)

    approvals = (
        db.query(models.Approval)
        .filter(
            models.Approval.plan_id == plan.id,
            models.Approval.plan_fingerprint == plan.spec_fingerprint,
        )
        .all()
    )
    approval_snapshot = {
        "approval_ids": [approval.id for approval in approvals],
        "approval_count": len(approvals),
    }
    execution_id = hashlib.sha1(
        f"{execution_key}:{datetime.datetime.utcnow().timestamp()}".encode("utf-8")
    ).hexdigest()
    execution = models.Execution(
        execution_id=execution_id,
        execution_key=execution_key,
        plan_id=plan.id,
        service_revision_id=plan.service_revision_id,
        policy_decision_id=decision.decision_id,
        policy_version=decision.policy_version,
        approval_snapshot=json.dumps(approval_snapshot, sort_keys=True),
        input_fingerprint=plan.spec_fingerprint,
        status=models.ExecutionStatus.PENDING,
        executor_type=LocalDeterministicExecutor.executor_type,
        executor_version=LocalDeterministicExecutor.executor_version,
        receipt=json.dumps({}, sort_keys=True),
    )
    db.add(execution)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        execution = (
            db.query(models.Execution)
            .filter(models.Execution.execution_key == execution_key)
            .first()
        )
        if not execution:
            raise HTTPException(status_code=409, detail="execution already in progress")
        return _build_execution_record_payload(execution)

    db.add(
        models.AuditEvent(
            event_type="EXECUTION_REQUESTED",
            actor=current_user.username,
            target=execution.execution_id,
            detail=plan.id,
        )
    )

    execution.status = models.ExecutionStatus.RUNNING
    db.add(
        models.AuditEvent(
            event_type="EXECUTION_STARTED",
            actor=current_user.username,
            target=execution.execution_id,
            detail=plan.id,
        )
    )

    spec_payload = json.loads(plan.service_revision.spec or "{}").get("spec", {})
    executor = LocalDeterministicExecutor()
    result = executor.execute(spec_payload)

    execution.status = (
        models.ExecutionStatus.SUCCEEDED
        if result.status == "SUCCEEDED"
        else models.ExecutionStatus.FAILED
    )
    execution.result_summary = result.summary
    execution.error_info = result.error_info
    execution.completed_at = datetime.datetime.utcnow()

    receipt = {
        "execution_id": execution.execution_id,
        "plan_id": plan.id,
        "service_revision_id": execution.service_revision_id,
        "policy_decision_id": decision.decision_id,
        "policy_version": decision.policy_version,
        "approval_snapshot": approval_snapshot,
        "input_fingerprint": plan.spec_fingerprint,
        "executor_type": execution.executor_type,
        "executor_version": execution.executor_version,
        "status": execution.status.value,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
        "result_summary": execution.result_summary,
        "error_info": execution.error_info,
        "metadata": result.metadata,
    }
    execution.receipt = json.dumps(receipt, sort_keys=True)

    if execution.status == models.ExecutionStatus.SUCCEEDED:
        plan.status = models.PlanStatus.APPLIED
        db.add(plan)
        db.add(
            models.AuditEvent(
                event_type="EXECUTION_SUCCEEDED",
                actor=current_user.username,
                target=execution.execution_id,
                detail=plan.id,
            )
        )
    else:
        db.add(
            models.AuditEvent(
                event_type="EXECUTION_FAILED",
                actor=current_user.username,
                target=execution.execution_id,
                detail=execution.error_info or "UNKNOWN_ERROR",
            )
        )

    db.commit()
    db.refresh(execution)
    return _build_execution_record_payload(execution)


@app.get("/executions/{execution_id}", response_model=ExecutionRecord)
def get_execution(
    execution_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    execution = (
        db.query(models.Execution)
        .filter(models.Execution.execution_id == execution_id)
        .first()
    )
    if not execution:
        raise HTTPException(status_code=404, detail="execution not found")
    return _build_execution_record_payload(execution)


@app.get("/plans/{plan_id}/executions", response_model=list[ExecutionRecord])
def get_plan_executions(
    plan_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    executions = (
        db.query(models.Execution)
        .filter(models.Execution.plan_id == plan_id)
        .order_by(models.Execution.created_at.asc())
        .all()
    )
    return [_build_execution_record_payload(item) for item in executions]


def run():
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
