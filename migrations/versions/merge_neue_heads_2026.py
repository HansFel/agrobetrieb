"""merge_neue_heads_2026

Revision ID: merge_neue_heads_2026
Revises: add_externe_apps, e5578613fbba
Create Date: 2026-03-19

"""
from alembic import op
import sqlalchemy as sa

revision = 'merge_neue_heads_2026'
down_revision = ('add_externe_apps', 'e5578613fbba')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
