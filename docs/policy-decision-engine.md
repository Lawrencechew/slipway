# Policy Decision Engine (Phase 5)

## Why this exists

PavedPath now includes a deterministic, server-side policy decision layer so request governance is explainable, reproducible, and auditable before approval.

No LLM, cloud API, or external policy service is used for authorization decisions.

## Flow

1. Developer submits/updates a `ServiceSpec`
2. Plan generation runs deterministic policy evaluation
3. Decision is persisted with policy version and reasons
4. Approval endpoint enforces the decision

## Decision model

Persisted policy decisions record:

- `decision_id`
- `plan_id`
- `outcome` (`PASS`, `REQUIRES_APPROVAL`, `BLOCKED`)
- `risk_level` (`LOW`, `MEDIUM`, `HIGH`)
- `policy_version` (`platform-policy-v1`)
- `reasons`
- `required_approvals`
- `blocking_violations`
- `advisory_warnings`
- `evaluated_at`
- staleness state (`is_stale`, `stale_reason`)

## Risk and outcome behavior

- **LOW**: outcome `PASS`, baseline approval requirement
- **MEDIUM**: outcome `REQUIRES_APPROVAL`, explicit platform-owner approval requirement
- **HIGH**: outcome `REQUIRES_APPROVAL`, stronger approval requirements (platform + security)
- **BLOCKED**: approval is denied server-side

## Policy versioning

Every decision stores `platform-policy-v1`.

This ensures the repository can explain which deterministic rule set produced a decision.

## Stale decision handling

When a service spec changes, prior active decisions for that service/fingerprint are marked stale.

Approval also verifies the plan fingerprint still matches the latest service revision; stale decisions are rejected and a new plan/evaluation is required.

## Server-side enforcement

Approval logic checks:

- plan state (`READY`)
- decision presence
- decision not stale
- decision outcome not `BLOCKED`
- required approval threshold derived from policy decision

Clients cannot bypass blocked or stale decisions by calling approval directly.

## Out of scope

- external policy engines (OPA/Cedar/SaaS)
- LLM-based risk decisions
- cloud provisioning or runtime infrastructure orchestration
- frontend redesigns or analytics dashboards
