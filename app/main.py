from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .schemas import ServiceSpec
from .planner import create_plan, fingerprint_spec
from .db import get_db
from sqlalchemy.orm import Session
from . import models
from .auth import get_current_user, create_user
from typing import Dict
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
def create_spec(spec: ServiceSpec, current_user: models.User = Depends(get_current_user)):
    # For v1 we keep specs in-memory or persist later
    # Validate basic fields
    if not spec.metadata.name:
        raise HTTPException(status_code=400, detail="metadata.name required")
    fp = fingerprint_spec(spec)
    # store minimal service and revision for spec
    db: Session = next(get_db())
    svc = db.query(models.Service).filter(models.Service.name == spec.metadata.name).first()
    if not svc:
        svc = models.Service(name=spec.metadata.name, owner=spec.metadata.owner, description=spec.metadata.description)
        db.add(svc)
        db.flush()
    # persist revision
    from .planner import persist_revision
    rev = persist_revision(db, svc, spec, fp)
    # audit
    ev = models.AuditEvent(event_type="SERVICE_SPEC_CREATED", actor=current_user.username, target=svc.name, detail=fp)
    db.add(ev)
    db.commit()
    return {"fingerprint": fp}


@app.post("/plans", status_code=201)
def plans_create(spec: ServiceSpec, current_user: models.User = Depends(get_current_user)):
    plan = create_plan(spec)
    # persist audit
    db: Session = next(get_db())
    ev = models.AuditEvent(event_type="PLAN_CREATED", actor=current_user.username, target=plan.id, detail=plan.spec_fingerprint)
    db.add(ev)
    db.commit()
    return plan.dict()


@app.post("/plans/{plan_id}/approve", status_code=200)
def approve_plan(plan_id: str, current_user: models.User = Depends(get_current_user)):
    # simple approval flow: create user if missing and record approval
    db: Session = next(get_db())
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")
    user = current_user
    # Ensure fingerprint binding
    if plan.status != models.Plan.status.type.python_type('READY') if hasattr(models.Plan.status, 'type') else 'READY':
        # allow only READY plans to be approved
        raise HTTPException(status_code=400, detail="only READY plans can be approved")
    approval = models.Approval(plan_id=plan_id, approver_id=user.id, plan_fingerprint=plan.spec_fingerprint)
    db.add(approval)
    plan.status = models.PlanStatus.APPROVED
    ev = models.AuditEvent(event_type="PLAN_APPROVED", actor=user.username, target=plan.id, detail=plan.spec_fingerprint)
    db.add(ev)
    db.commit()
    return {"approved": True, "plan_id": plan_id}


def run():
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
