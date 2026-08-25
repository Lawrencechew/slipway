"""add executions

Revision ID: 0004_add_executions
Revises: 0003_add_policy_decisions
Create Date: 2026-08-25
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_add_executions"
down_revision = "0003_add_policy_decisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "executions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("execution_id", sa.String(64), nullable=False, unique=True),
        sa.Column("execution_key", sa.String(128), nullable=False, unique=True),
        sa.Column("plan_id", sa.String(64), sa.ForeignKey("plans.id"), nullable=False),
        sa.Column("service_revision_id", sa.Integer, sa.ForeignKey("service_revisions.id"), nullable=False),
        sa.Column("policy_decision_id", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.Column("approval_snapshot", sa.Text, nullable=False),
        sa.Column("input_fingerprint", sa.String(128), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("executor_type", sa.String(100), nullable=False),
        sa.Column("executor_version", sa.String(50), nullable=False),
        sa.Column("result_summary", sa.Text),
        sa.Column("error_info", sa.Text),
        sa.Column("receipt", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_executions_execution_id", "executions", ["execution_id"], unique=True)
    op.create_index("ix_executions_execution_key", "executions", ["execution_key"], unique=True)


def downgrade():
    op.drop_index("ix_executions_execution_key", table_name="executions")
    op.drop_index("ix_executions_execution_id", table_name="executions")
    op.drop_table("executions")
