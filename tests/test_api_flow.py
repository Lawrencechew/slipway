import json
from starlette.testclient import TestClient
from app.main import app

client = TestClient(app)
from app.db import engine, Base, SessionLocal
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
        "apiVersion": "slipway.dev/v1",
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
    assert plan.get("policy_decision", {}).get("policy_version") == "platform-policy-v1"
    plan_id = plan.get("id")

    # approve
    r = client.post(f"/plans/{plan_id}/approve", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body.get("approved") is True

    # audit events persisted
    db = SessionLocal()
    try:
        events = db.query(models.AuditEvent).all()
        assert any(e.event_type == "SERVICE_SPEC_CREATED" for e in events)
        assert any(e.event_type == "PLAN_CREATED" for e in events)
        assert any(e.event_type == "PLAN_APPROVED" for e in events)
    finally:
        db.close()


def test_blocked_policy_cannot_be_approved():
    r = client.post("/users", json={"username": "blocked-user", "display_name": "Blocked"})
    assert r.status_code == 201
    token = r.json()["api_key"]
    headers = {"Authorization": f"Bearer {token}"}

    blocked_spec = {
        "apiVersion": "slipway.dev/v1",
        "kind": "Service",
        "metadata": {"name": "blocked-service", "owner": "security"},
        "spec": {
            "runtime": {"language": "python", "version": "3.13"},
            "deployment": {"environment": "production", "replicas": 3},
            "network": {"public": True},
            "data": {"sensitivity": "high"},
            "resources": {"limits": {"cpu": "250m"}},
            "containers": [{
                "name": "app",
                "securityContext": {"runAsNonRoot": True},
                "readinessProbe": {"httpGet": {"path": "/health"}},
                "livenessProbe": {"httpGet": {"path": "/health"}}
            }],
            "podDisruptionBudget": {"minAvailable": 1},
            "observability": {"metrics": True}
        },
    }

    plan_resp = client.post("/plans", json=blocked_spec, headers=headers)
    assert plan_resp.status_code == 201
    plan = plan_resp.json()
    assert plan["status"] == "INVALID"
    assert plan["policy_decision"]["outcome"] == "BLOCKED"

    approve_resp = client.post(f"/plans/{plan['id']}/approve", headers=headers)
    assert approve_resp.status_code == 400
    assert "only READY plans can be approved" in approve_resp.json()["detail"]


def test_stale_policy_decision_rejected_after_spec_update():
    r = client.post("/users", json={"username": "stale-user", "display_name": "Stale"})
    assert r.status_code == 201
    token = r.json()["api_key"]
    headers = {"Authorization": f"Bearer {token}"}

    base_spec = {
        "apiVersion": "slipway.dev/v1",
        "kind": "Service",
        "metadata": {"name": "stale-service", "owner": "platform"},
        "spec": {
            "runtime": {"language": "python", "version": "3.13"},
            "deployment": {"environment": "staging", "replicas": 2},
            "network": {"public": False},
            "data": {"sensitivity": "low"},
            "resources": {"limits": {"cpu": "250m"}},
            "containers": [{
                "name": "app",
                "securityContext": {"runAsNonRoot": True},
                "readinessProbe": {"httpGet": {"path": "/health"}},
                "livenessProbe": {"httpGet": {"path": "/health"}}
            }],
            "observability": {"metrics": True}
        },
    }

    plan_resp = client.post("/plans", json=base_spec, headers=headers)
    assert plan_resp.status_code == 201
    plan = plan_resp.json()
    assert plan["status"] == "READY"

    updated_spec = json.loads(json.dumps(base_spec))
    updated_spec["spec"]["network"]["public"] = True
    spec_resp = client.post("/specs", json=updated_spec, headers=headers)
    assert spec_resp.status_code == 201

    approve_resp = client.post(f"/plans/{plan['id']}/approve", headers=headers)
    assert approve_resp.status_code == 409
    assert "stale" in approve_resp.json()["detail"].lower()
