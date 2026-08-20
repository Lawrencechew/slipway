from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from .schemas import ServiceSpec
from .planner import create_plan, fingerprint_spec
from .db import get_db
from sqlalchemy.orm import Session
from . import models
import uvicorn

app = FastAPI(title="PavedPath API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/specs", status_code=201)
def create_spec(spec: ServiceSpec):
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
    return {"fingerprint": fp}


@app.post("/plans", status_code=201)
def plans_create(spec: ServiceSpec):
    plan = create_plan(spec)
    return plan.dict()


@app.post("/plans/{plan_id}/approve", status_code=200)
def approve_plan(plan_id: str, approver: str):
    # simple approval flow: create user if missing and record approval
    db: Session = next(get_db())
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="plan not found")
    user = db.query(models.User).filter(models.User.username == approver).first()
    if not user:
        user = models.User(username=approver, display_name=approver)
        db.add(user)
        db.flush()
    # Ensure fingerprint binding
    approval = models.Approval(plan_id=plan_id, approver_id=user.id, plan_fingerprint=plan.spec_fingerprint)
    db.add(approval)
    plan.status = models.Plan.status.type.python_type('APPROVED') if hasattr(models.Plan.status, 'type') else 'APPROVED'
    try:
        from .models import PlanStatus
        plan.status = PlanStatus.APPROVED
    except Exception:
        plan.status = 'APPROVED'
    db.commit()
    return {"approved": True, "plan_id": plan_id}


def run():
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    run()
