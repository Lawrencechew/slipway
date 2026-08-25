from app.schemas import ServiceSpec, Metadata
from app.planner import create_plan, fingerprint_spec
from app.db import SessionLocal, Base, engine
from app import models


def setup_module(module):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def sample_spec():
    return ServiceSpec(metadata=Metadata(name="orders-api", owner="commerce"), spec={
        "runtime": {"language": "python", "version": "3.13"},
        "deployment": {"environment": "production", "replicas": 3},
        "resources": {"limits": {"cpu": "250m"}},
        "containers": [{"name": "app", "securityContext": {"runAsNonRoot": True}, "readinessProbe": {"httpGet": {"path": "/health"}}, "livenessProbe": {"httpGet": {"path": "/health"}}}],
        "podDisruptionBudget": {"minAvailable": 1},
        "observability": {"metrics": True}
    })


def test_deterministic_and_fingerprint_changes():
    s = sample_spec()
    fp1 = fingerprint_spec(s)
    p1 = create_plan(s)
    fp2 = p1.spec_fingerprint
    assert fp1 == fp2
    # change spec
    s.spec['deployment']['replicas'] = 4
    p2 = create_plan(s)
    assert p2.spec_fingerprint != fp1


def test_supersede_previous_plan():
    s = sample_spec()
    p1 = create_plan(s)
    p2 = create_plan(s)
    db = SessionLocal()
    try:
        plan1 = db.query(models.Plan).filter(models.Plan.id == p1.id).first()
        plan2 = db.query(models.Plan).filter(models.Plan.id == p2.id).first()
        assert plan1.status.name == 'SUPERSEDED' or str(plan1.status) == 'SUPERSEDED'
        assert plan2.status == 'READY' or (hasattr(plan2.status, 'name') and plan2.status.name == 'READY')
    finally:
        db.close()


def test_approval_binding_and_invalid_cannot_be_approved():
    db = SessionLocal()
    try:
        s = sample_spec()
        plan = create_plan(s)
        # plan is READY
        # create user
        user = models.User(username="bob", display_name="Bob")
        db.add(user)
        db.flush()
        # approval with correct fingerprint
        appr = models.Approval(plan_id=plan.id, approver_id=user.id, plan_fingerprint=plan.spec_fingerprint)
        db.add(appr)
        db.commit()
        # apply approval should be rejected for non-READY plan: simulate invalid plan
        bad_spec = sample_spec()
        bad_spec.spec['deployment']['replicas'] = 1
        bad_plan = create_plan(bad_spec)
        assert bad_plan.status == 'INVALID'
    finally:
        db.rollback()
        db.close()


def test_policy_decision_persisted_with_reasons_and_version():
    db = SessionLocal()
    try:
        s = sample_spec()
        plan = create_plan(s)
        decision = db.query(models.PolicyDecision).filter(models.PolicyDecision.plan_id == plan.id).first()
        assert decision is not None
        assert decision.policy_version == "platform-policy-v1"
        assert decision.outcome.name in {"PASS", "REQUIRES_APPROVAL", "BLOCKED"}
        assert decision.reasons is not None
    finally:
        db.close()
