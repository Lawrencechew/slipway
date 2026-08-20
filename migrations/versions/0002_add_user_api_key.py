"""add user api_key

Revision ID: 0002_add_user_api_key
Revises: 0001_initial
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0002_add_user_api_key'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('api_key', sa.String(128), unique=True, nullable=True))


def downgrade():
    op.drop_column('users', 'api_key')
