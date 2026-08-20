"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('display_name', sa.String(200)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table('services',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(200), nullable=False, unique=True),
        sa.Column('owner', sa.String(200)),
        sa.Column('description', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table('service_revisions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('service_id', sa.Integer, sa.ForeignKey('services.id'), nullable=False),
        sa.Column('revision', sa.Integer, nullable=False),
        sa.Column('spec', sa.Text, nullable=False),
        sa.Column('fingerprint', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table('plans',
        sa.Column('id', sa.String(64), primary_key=True),
        sa.Column('service_revision_id', sa.Integer, sa.ForeignKey('service_revisions.id'), nullable=False),
        sa.Column('spec_fingerprint', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('artifacts', sa.Text),
    )

    op.create_table('policy_results',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('plan_id', sa.String(64), sa.ForeignKey('plans.id'), nullable=False),
        sa.Column('policy', sa.String(200)),
        sa.Column('status', sa.String(50)),
        sa.Column('severity', sa.String(50)),
        sa.Column('explanation', sa.Text),
        sa.Column('remediation', sa.Text),
    )

    op.create_table('approvals',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('plan_id', sa.String(64), sa.ForeignKey('plans.id'), nullable=False),
        sa.Column('approver_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('plan_fingerprint', sa.String(128), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table('git_operations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('plan_id', sa.String(64), sa.ForeignKey('plans.id'), nullable=False),
        sa.Column('operation', sa.String(50)),
        sa.Column('result', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table('audit_events',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('actor', sa.String(200)),
        sa.Column('target', sa.String(200)),
        sa.Column('detail', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade():
    op.drop_table('audit_events')
    op.drop_table('git_operations')
    op.drop_table('approvals')
    op.drop_table('policy_results')
    op.drop_table('plans')
    op.drop_table('service_revisions')
    op.drop_table('services')
    op.drop_table('users')
