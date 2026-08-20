import json
import pytest
from app.main import app

# Try several ASGI test client constructors and fall back to skipping tests if none work.
client = None
for ctor in (
    # prefer FastAPI wrapper
    lambda: __import__('fastapi.testclient', fromlist=['TestClient']).TestClient(app),
    # starlette
    lambda: __import__('starlette.testclient', fromlist=['TestClient']).TestClient(app),
    # httpx
    lambda: __import__('httpx', fromlist=['Client']).Client(app=app, base_url="http://testserver"),
):
    try:
        client = ctor()
        break
    except Exception:
        client = None

pytestmark = pytest.mark.skipif(client is None, reason="No compatible ASGI test client available in this environment")
from app.db import engine, Base
from app import models


# client is either an ASGI-capable test client or None (tests will be skipped)


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
