from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .db import Base
import enum


class PlanStatus(enum.Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    INVALID = "INVALID"
    READY = "READY"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    FAILED = "FAILED"
    SUPERSEDED = "SUPERSEDED"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    api_key = Column(String(128), unique=True, nullable=True)
    display_name = Column(String(200))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Service(Base):
    __tablename__ = "services"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), unique=True, nullable=False)
    owner = Column(String(200))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    revisions = relationship("ServiceRevision", back_populates="service")


class ServiceRevision(Base):
    __tablename__ = "service_revisions"
    id = Column(Integer, primary_key=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    revision = Column(Integer, nullable=False)
    spec = Column(Text, nullable=False)
    fingerprint = Column(String(128), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    service = relationship("Service", back_populates="revisions")


class Plan(Base):
    __tablename__ = "plans"
    id = Column(String(64), primary_key=True)
    service_revision_id = Column(Integer, ForeignKey("service_revisions.id"), nullable=False)
    spec_fingerprint = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(PlanStatus), nullable=False, default=PlanStatus.DRAFT)
    artifacts = Column(Text)
    service_revision = relationship("ServiceRevision")
    approvals = relationship("Approval", back_populates="plan")


class PolicyResult(Base):
    __tablename__ = "policy_results"
    id = Column(Integer, primary_key=True)
    plan_id = Column(String(64), ForeignKey("plans.id"), nullable=False)
    policy = Column(String(200))
    status = Column(String(50))
    severity = Column(String(50))
    explanation = Column(Text)
    remediation = Column(Text)


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(Integer, primary_key=True)
    plan_id = Column(String(64), ForeignKey("plans.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan_fingerprint = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    plan = relationship("Plan", back_populates="approvals")
    approver = relationship("User")


class GitOperation(Base):
    __tablename__ = "git_operations"
    id = Column(Integer, primary_key=True)
    plan_id = Column(String(64), ForeignKey("plans.id"), nullable=False)
    operation = Column(String(50))
    result = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id = Column(Integer, primary_key=True)
    event_type = Column(String(100), nullable=False)
    actor = Column(String(200))
    target = Column(String(200))
    detail = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
