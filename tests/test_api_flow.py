import json
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)
from app.db import engine, Base
from app import models


def setup_module(module):
    # ensure fresh DB (sqlite by default for local tests)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_user_and_happy_path():
    # create user
    r = client.post("/users", json={"username": "alice", "display_name": "Alice"})
    assert r.status_code == 201
    body = r.json()
    assert "api_key" in body
    token = body["api_key"]

    headers = {"Authorization": f"Bearer {token}"}

    spec = {
        "apiVersion": "pavedpath.dev/v1",
        "kind": "Service",
        "metadata": {"name": "orders-api", "owner": "commerce"},
        "spec": {"runtime": {"language": "python", "version": "3.13"}, "deployment": {"environment": "production", "replicas": 3}, "resources": {"limits": {"cpu": "250m"}}, "containers": [{"name": "app", "securityContext": {"runAsNonRoot": True}, "readinessProbe": {"httpGet": {"path": "/health"}}, "livenessProbe": {"httpGet": {"path": "/health"}}}], "podDisruptionBudget": {"minAvailable": 1}, "observability": {"metrics": True}}
    }

    r = client.post("/specs", json=spec, headers=headers)
    assert r.status_code == 201
    fp = r.json().get("fingerprint")
    assert isinstance(fp, str) and len(fp) == 64

    # create plan
    r = client.post("/plans", json=spec, headers=headers)
    assert r.status_code == 201
    plan = r.json()
    assert plan.get("status") == "READY"
    plan_id = plan.get("id")

    # approve
    r = client.post(f"/plans/{plan_id}/approve", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("approved") is True

    # audit events persisted
    db = next(__import__('app').db.get_db())
    events = db.query(models.AuditEvent).all()
    assert any(e.event_type == "SERVICE_SPEC_CREATED" for e in events)
    assert any(e.event_type == "PLAN_CREATED" for e in events)
    assert any(e.event_type == "PLAN_APPROVED" for e in events)
