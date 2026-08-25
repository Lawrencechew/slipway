"""add policy decisions

Revision ID: 0003_add_policy_decisions
Revises: 0002_add_user_api_key
Create Date: 2026-08-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_add_policy_decisions"
down_revision = "0002_add_user_api_key"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "policy_decisions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("decision_id", sa.String(64), nullable=False, unique=True),
        sa.Column("plan_id", sa.String(64), sa.ForeignKey("plans.id"), nullable=False, unique=True),
        sa.Column("spec_fingerprint", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(50), nullable=False),
        sa.Column("risk_level", sa.String(50), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("reasons", sa.Text, nullable=False),
        sa.Column("required_approvals", sa.Text, nullable=False),
        sa.Column("blocking_violations", sa.Text, nullable=False),
        sa.Column("advisory_warnings", sa.Text, nullable=False),
        sa.Column("is_stale", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("stale_reason", sa.Text),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_policy_decisions_decision_id", "policy_decisions", ["decision_id"], unique=True)


def downgrade():
    op.drop_index("ix_policy_decisions_decision_id", table_name="policy_decisions")
    op.drop_table("policy_decisions")
