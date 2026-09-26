import React, { useState } from "react";

type PlanResponse = {
  id: string;
  status: string;
  artifacts: Array<{ path: string; reason: string }>;
  policy_decision?: {
    outcome: string;
    risk_level: string;
    policy_version: string;
    reasons: Array<{ code: string; message: string }>;
    required_approvals: string[];
    blocking_violations: Array<{ code: string; message: string }>;
  };
};

type ExecutionResponse = {
  execution_id: string;
  status: string;
  policy_version: string;
  result_summary?: string;
  error_info?: string;
};

function Login({ onSetToken }: { onSetToken: (t: string) => void }) {
  const [name, setName] = useState("alice");

  async function create() {
    const r = await fetch("/users", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username: name }),
    });
    const j = await r.json();
    localStorage.setItem("api_key", j.api_key);
    onSetToken(j.api_key);
  }

  return (
    <div>
      <h3>Sign in</h3>
      <input value={name} onChange={(e) => setName(e.target.value)} />
      <button onClick={create}>Create API Key</button>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem("api_key"));
  const [view, setView] = useState<"dash" | "create" | "plan" | "audit">("dash");
  const [specBody, setSpecBody] = useState("");
  const [plan, setPlan] = useState<PlanResponse | null>(null);
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [executionError, setExecutionError] = useState<string | null>(null);

  if (!token) {
    return <Login onSetToken={(t) => { setToken(t); setView("dash"); }} />;
  }

  const authHeaders = {
    "content-type": "application/json",
    authorization: `Bearer ${token}`,
  };

  async function createSpec() {
    const spec = JSON.parse(specBody);
    const r = await fetch("/specs", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(spec),
    });
    const j = await r.json();
    if (!r.ok) {
      alert(j?.detail || "Failed to save spec");
      return;
    }
    alert(`Spec created: ${j.fingerprint}`);
  }

  async function genPlan() {
    const spec = JSON.parse(specBody);
    const r = await fetch("/plans", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(spec),
    });
    const j = await r.json();
    if (!r.ok) {
      alert(j?.detail || "Failed to generate plan");
      return;
    }
    setPlan(j);
    setExecution(null);
    setExecutionError(null);
    setView("plan");
  }

  async function approve() {
    if (!plan) return;
    const r = await fetch(`/plans/${plan.id}/approve`, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
    });
    const j = await r.json();
    if (!r.ok) {
      alert(j?.detail || "Approval failed");
      return;
    }
    if (j.approved) {
      alert("Plan approved");
      setPlan({ ...plan, status: "APPROVED" });
    } else {
      alert(`Approval recorded (${j.approval_count}/${j.required_approval_count})`);
    }
  }

  async function executePlan() {
    if (!plan) return;
    setExecutionError(null);
    const r = await fetch(`/plans/${plan.id}/execute`, {
      method: "POST",
      headers: { authorization: `Bearer ${token}` },
    });
    const j = await r.json();
    if (!r.ok) {
      setExecutionError(j?.detail || "Execution rejected");
      return;
    }
    setExecution(j);
    if (j.status === "SUCCEEDED") {
      setPlan({ ...plan, status: "APPLIED" });
    }
  }

  return (
    <div style={{ fontFamily: "Inter, system-ui", padding: 20 }}>
      <h1>Slipway (Demo)</h1>
      <div style={{ marginBottom: 10 }}>
        <button onClick={() => setView("dash")}>Dashboard</button>
        <button onClick={() => setView("create")}>Create Service</button>
        <button onClick={() => setView("audit")}>Audit</button>
      </div>

      {view === "dash" && (
        <div>
          <h2>Dashboard</h2>
          <p>Use Create Service to submit a ServiceSpec JSON.</p>
        </div>
      )}

      {view === "create" && (
        <div>
          <h2>Create Service</h2>
          <textarea
            style={{ width: "100%", height: 240 }}
            value={specBody}
            onChange={(e) => setSpecBody(e.target.value)}
            placeholder="Paste ServiceSpec JSON here"
          />
          <div style={{ marginTop: 8 }}>
            <button onClick={createSpec}>Save Spec</button>
            <button onClick={genPlan}>Generate Plan</button>
          </div>
        </div>
      )}

      {view === "plan" && plan && (
        <div>
          <h2>Plan: {plan.id}</h2>
          <p>Status: {plan.status}</p>
          {plan.policy_decision && (
            <div style={{ border: "1px solid #ccc", padding: 12, borderRadius: 8, marginBottom: 12 }}>
              <h3>Policy Decision</h3>
              <p><strong>Outcome:</strong> {plan.policy_decision.outcome}</p>
              <p><strong>Risk:</strong> {plan.policy_decision.risk_level}</p>
              <p><strong>Policy Version:</strong> {plan.policy_decision.policy_version}</p>
              <p><strong>Why:</strong></p>
              <ul>
                {plan.policy_decision.reasons.map((r, i) => (
                  <li key={i}>{r.code} — {r.message}</li>
                ))}
              </ul>
              <p><strong>Required Approvals:</strong></p>
              <ul>
                {plan.policy_decision.required_approvals.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
              {plan.policy_decision.blocking_violations?.length > 0 && (
                <>
                  <p><strong>Blocking Violations:</strong></p>
                  <ul>
                    {plan.policy_decision.blocking_violations.map((b, i) => (
                      <li key={i}>{b.code} — {b.message}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}

          <h3>Artifacts</h3>
          <ul>
            {plan.artifacts.map((a, i) => (
              <li key={i}>{a.path} — {a.reason}</li>
            ))}
          </ul>

          <button onClick={approve}>Approve</button>
          <button onClick={executePlan} style={{ marginLeft: 8 }}>Execute</button>

          {executionError && <p style={{ color: "crimson" }}>{executionError}</p>}
          {execution && (
            <div style={{ border: "1px solid #ccc", padding: 12, borderRadius: 8, marginTop: 12 }}>
              <h3>Execution Receipt</h3>
              <p><strong>Execution ID:</strong> {execution.execution_id}</p>
              <p><strong>Status:</strong> {execution.status}</p>
              <p><strong>Policy Version:</strong> {execution.policy_version}</p>
              <p><strong>Result:</strong> {execution.result_summary || "n/a"}</p>
              {execution.error_info && <p><strong>Error:</strong> {execution.error_info}</p>}
            </div>
          )}
        </div>
      )}

      {view === "audit" && (
        <div>
          <h2>Audit</h2>
          <p>Use API execution and audit endpoints to inspect history.</p>
        </div>
      )}
    </div>
  );
}
