# Design Decisions (Concise)

- Git-native workflow: Git provides a single source-of-truth, reviewability, and CI-driven deployment. Slipway emits Git-ready artifacts rather than mutating infra directly.
- Deterministic planners: plans are fingerprinted so reviews and approvals are reproducible and auditable.
- Approval binding: approvals store the plan/revision fingerprint to prevent approving a changed desired state.
- PostgreSQL for persistence: durable, relational model fits revision/approval/ audit semantics and makes testing deterministic.
- Simple API-key auth (v1): replaceable mechanism to demonstrate approval provenance without integrating external identity providers.
