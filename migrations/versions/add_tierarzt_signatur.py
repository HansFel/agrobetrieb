"""Add signatur fields to tierarzt_besuch

Revision ID: add_tierarzt_signatur
Revises: 6dbb8fee6795
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_tierarzt_signatur'
down_revision = '6dbb8fee6795'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('tierarzt_besuch') as batch_op:
        batch_op.add_column(sa.Column('signatur_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('signatur_datum', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('signatur_name', sa.String(200), nullable=True))


def downgrade():
    with op.batch_alter_table('tierarzt_besuch') as batch_op:
        batch_op.drop_column('signatur_name')
        batch_op.drop_column('signatur_datum')
        batch_op.drop_column('signatur_data')
