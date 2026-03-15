"""Add signatur fields to rind_arzneimittel_anwendung (TAMG Milchvieh)

Revision ID: add_tamg_signatur_milchvieh
Revises: add_tierarzt_signatur
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_tamg_signatur_milchvieh'
down_revision = 'add_tierarzt_signatur'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('rind_arzneimittel_anwendung') as batch_op:
        batch_op.add_column(sa.Column('signatur_data', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('signatur_datum', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('signatur_name', sa.String(200), nullable=True))


def downgrade():
    with op.batch_alter_table('rind_arzneimittel_anwendung') as batch_op:
        batch_op.drop_column('signatur_name')
        batch_op.drop_column('signatur_datum')
        batch_op.drop_column('signatur_data')
