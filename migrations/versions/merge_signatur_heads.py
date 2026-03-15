"""Merge signatur branch with main branch

Revision ID: merge_signatur_heads
Revises: a6327bd1caa5, add_tamg_signatur_milchvieh
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'merge_signatur_heads'
down_revision = ('a6327bd1caa5', 'add_tamg_signatur_milchvieh')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
