import json

from starlette.testclient import TestClient

from app import models
from app.db import Base, SessionLocal, engine
from app.main import app

client = TestClient(app)


def setup_module(module):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _create_user(username: str):
    resp = client.post("/users", json={"username": username, "display_name": username})
    assert resp.status_code == 201
    token = resp.json()["api_key"]
    return {"Authorization": f"Bearer {token}"}


def _base_spec(name: str, *, environment: str = "staging", public: bool = False, sensitivity: str = "low"):
    return {
        "apiVersion": "pavedpath.dev/v1",
        "kind": "Service",
        "metadata": {"name": name, "owner": "platform"},
        "spec": {
            "runtime": {"language": "python", "version": "3.13"},
            "deployment": {"environment": environment, "replicas": 2},
            "network": {"public": public},
            "data": {"sensitivity": sensitivity},
            "resources": {"limits": {"cpu": "250m"}},
            "containers": [
                {
                    "name": "app",
                    "securityContext": {"runAsNonRoot": True},
                    "readinessProbe": {"httpGet": {"path": "/health"}},
                    "livenessProbe": {"httpGet": {"path": "/health"}},
                }
            ],
            "observability": {"metrics": True},
        },
    }


def _create_plan(headers, spec):
    resp = client.post("/plans", json=spec, headers=headers)
    assert resp.status_code == 201
    return resp.json()


def _approve_plan(headers, plan_id):
    resp = client.post(f"/plans/{plan_id}/approve", headers=headers)
    assert resp.status_code == 200
    return resp.json()


def test_approved_current_plan_executes_successfully():
    headers = _create_user("exec-success")
    plan = _create_plan(headers, _base_spec("svc-exec-success"))
    approval = _approve_plan(headers, plan["id"])
    assert approval["approved"] is True

    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert execute.status_code == 200
    body = execute.json()
    assert body["status"] == "SUCCEEDED"
    assert body["plan_id"] == plan["id"]


def test_unapproved_plan_cannot_execute():
    headers = _create_user("exec-unapproved")
    plan = _create_plan(headers, _base_spec("svc-unapproved"))

    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert execute.status_code == 400
    assert "not approved" in execute.json()["detail"].lower()


def test_blocked_policy_cannot_execute():
    headers = _create_user("exec-blocked")
    blocked = _base_spec(
        "svc-blocked", environment="production", public=True, sensitivity="high"
    )
    plan = _create_plan(headers, blocked)
    assert plan["policy_decision"]["outcome"] == "BLOCKED"

    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert execute.status_code == 400


def test_stale_policy_decision_cannot_execute():
    headers = _create_user("exec-stale")
    spec = _base_spec("svc-stale")
    plan = _create_plan(headers, spec)
    approval = _approve_plan(headers, plan["id"])
    assert approval["approved"] is True

    changed = json.loads(json.dumps(spec))
    changed["spec"]["network"]["public"] = True
    resp = client.post("/specs", json=changed, headers=headers)
    assert resp.status_code == 201

    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert execute.status_code == 409
    assert "stale" in execute.json()["detail"].lower()


def test_execution_receipt_contains_expected_references():
    headers = _create_user("exec-receipt")
    plan = _create_plan(headers, _base_spec("svc-receipt"))
    approval = _approve_plan(headers, plan["id"])
    assert approval["approved"] is True
    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert execute.status_code == 200
    body = execute.json()
    receipt = body["receipt"]
    assert receipt["execution_id"] == body["execution_id"]
    assert receipt["plan_id"] == plan["id"]
    assert receipt["policy_version"] == "platform-policy-v1"
    assert receipt["input_fingerprint"] == plan["spec_fingerprint"]


def test_duplicate_execution_request_is_idempotent():
    headers = _create_user("exec-idempotent")
    plan = _create_plan(headers, _base_spec("svc-idempotent"))
    approval = _approve_plan(headers, plan["id"])
    assert approval["approved"] is True

    first = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    second = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["execution_id"] == second.json()["execution_id"]


def test_completed_execution_evidence_not_mutable_via_api():
    headers = _create_user("exec-immutability")
    plan = _create_plan(headers, _base_spec("svc-immutability"))
    approval = _approve_plan(headers, plan["id"])
    assert approval["approved"] is True
    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    execution_id = execute.json()["execution_id"]

    put_resp = client.put(f"/executions/{execution_id}", headers=headers, json={"status": "FAILED"})
    delete_resp = client.delete(f"/executions/{execution_id}", headers=headers)
    assert put_resp.status_code == 405
    assert delete_resp.status_code == 405


def test_execution_failure_remains_persisted():
    headers = _create_user("exec-failure")
    failing = _base_spec("svc-failure")
    failing["spec"]["execution"] = {"simulateFailure": True}
    plan = _create_plan(headers, failing)
    approval = _approve_plan(headers, plan["id"])
    assert approval["approved"] is True

    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert execute.status_code == 200
    body = execute.json()
    assert body["status"] == "FAILED"
    assert body["error_info"] == "SIMULATED_EXECUTION_FAILURE"

    get_resp = client.get(f"/executions/{body['execution_id']}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "FAILED"


def test_execution_audit_history_records_lifecycle():
    headers = _create_user("exec-audit")
    plan = _create_plan(headers, _base_spec("svc-audit"))
    approval = _approve_plan(headers, plan["id"])
    assert approval["approved"] is True
    execute = client.post(f"/plans/{plan['id']}/execute", headers=headers)
    assert execute.status_code == 200
    execution_id = execute.json()["execution_id"]

    db = SessionLocal()
    try:
        events = (
            db.query(models.AuditEvent)
            .filter(models.AuditEvent.target == execution_id)
            .all()
        )
        types = {event.event_type for event in events}
        assert "EXECUTION_REQUESTED" in types
        assert "EXECUTION_STARTED" in types
        assert "EXECUTION_SUCCEEDED" in types
    finally:
        db.close()

    history = client.get(f"/plans/{plan['id']}/executions", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) >= 1
