"""Add password_last_changed to user

Revision ID: 1234567890ab
Revises: abcdef123456
Create Date: 2025-09-09 13:10:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1234567890ab'
down_revision = 'abcdef123456'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('password_last_changed', sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column('user', 'password_last_changed')