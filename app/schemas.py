from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class Metadata(BaseModel):
    name: str
    owner: Optional[str] = None
    description: Optional[str] = None


class Runtime(BaseModel):
    language: str
    version: str


class Deployment(BaseModel):
    environment: str
    replicas: Optional[int] = 1


class Network(BaseModel):
    public: bool = False


class Resources(BaseModel):
    profile: Optional[str] = "small"


class Observability(BaseModel):
    metrics: bool = False
    tracing: bool = False


class SLO(BaseModel):
    availability: Optional[float]


class ServiceSpec(BaseModel):
    apiVersion: str = Field("pavedpath.dev/v1")
    kind: str = Field("Service")
    metadata: Metadata
    spec: dict

    def dict_canonical(self):
        # Return canonical dict used for fingerprinting
        return {
            "apiVersion": self.apiVersion,
            "kind": self.kind,
            "metadata": self.metadata.dict(),
            "spec": self.spec,
        }


class PolicyResult(BaseModel):
    policy: str
    status: str
    severity: str
    explanation: str
    remediation: Optional[str]


class PolicyDecisionSummary(BaseModel):
    decision_id: str
    outcome: str
    risk_level: str
    policy_version: str
    reasons: List[Dict[str, str]] = []
    required_approvals: List[str] = []
    blocking_violations: List[Dict[str, str]] = []
    advisory_warnings: List[Dict[str, str]] = []
    evaluated_at: Optional[str] = None
    is_stale: bool = False
    stale_reason: Optional[str] = None


class Plan(BaseModel):
    id: str
    spec_fingerprint: str
    created: str
    status: str
    policy_results: List[PolicyResult] = []
    policy_decision: Optional[PolicyDecisionSummary] = None
    artifacts: List[Dict[str, Any]] = []
