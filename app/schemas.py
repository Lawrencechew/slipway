from pydantic import BaseModel, Field
from typing import List, Optional


class Metadata(BaseModel):
    name: str
    owner: Optional[str]
    description: Optional[str]


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


class Plan(BaseModel):
    id: str
    spec_fingerprint: str
    created: str
    status: str
    policy_results: List[PolicyResult] = []
    artifacts: dict = {}
