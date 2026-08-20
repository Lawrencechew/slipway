import json
from app.schemas import ServiceSpec, Metadata
from app.planner import create_plan, fingerprint_spec
from app.db import SessionLocal
from app import models
import datetime


def make_spec():
    return ServiceSpec(
        metadata=Metadata(name="orders-api", owner="commerce", description="Demo acceptance test"),
        spec={
            "runtime": {"language": "python", "version": "3.13"},
            "deployment": {"environment": "production", "replicas": 3},
            "resources": {"limits": {"cpu": "500m", "memory": "512Mi"}},
            "observability": {"metrics": True, "tracing": True},
                "containers": [{"name": "app", "securityContext": {"runAsNonRoot": True}, "readinessProbe": {"httpGet": {"path": "/health"}}, "livenessProbe": {"httpGet": {"path": "/health"}} }],
                "secrets": ["DATABASE_URL"],
                "podDisruptionBudget": {"minAvailable": 1},
            "slo": {"availability": 99.9},
        },
    )


def run_demo():
    print('Creating plan from spec...')
    spec = make_spec()
    plan = create_plan(spec)
    print('Plan created:', plan.id, 'fingerprint:', plan.spec_fingerprint)

    db = SessionLocal()
    try:
        plan_row = db.query(models.Plan).filter(models.Plan.id == plan.id).first()
        print('Plan row status:', plan_row.status)

        # Approve plan
        user = db.query(models.User).filter(models.User.username == 'approver').first()
        if not user:
            user = models.User(username='approver', display_name='Approver')
            db.add(user)
            db.flush()
        approval = models.Approval(plan_id=plan.id, approver_id=user.id, plan_fingerprint=plan.spec_fingerprint)
        db.add(approval)
        try:
            from app.models import PlanStatus
            plan_row.status = PlanStatus.APPROVED
        except Exception:
            plan_row.status = 'APPROVED'
        db.commit()
        print('Plan approved, status now:', plan_row.status)

        # Create new revision (change spec)
        print('Creating revised spec (replicas->2)...')
        spec2 = make_spec()
        spec2.spec['deployment']['replicas'] = 2
        plan2 = create_plan(spec2)
        print('New plan created:', plan2.id, 'fingerprint:', plan2.spec_fingerprint)

        approvals_for_new = db.query(models.Approval).filter(models.Approval.plan_id == plan2.id).all()
        print('Approvals for new plan:', len(approvals_for_new))
        assert len(approvals_for_new) == 0, 'New plan should not inherit approvals'

    finally:
        db.close()


if __name__ == '__main__':
    run_demo()
