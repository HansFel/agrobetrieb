"""Add signatur fields to rind_arzneimittel_anwendung (TAMG Milchvieh)

Revision ID: add_tamg_signatur_milchvieh
Revises: add_tierarzt_signatur
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_tamg_signatur_milchvieh'
down_revision = 'add_tierarzt_signatur'
branch_labels = None
depends_on = None


def _table_exists(table_name):
    conn = op.get_bind()
    return conn.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
    ), {'t': table_name}).fetchone() is not None


def _add_column_if_not_exists(table, column_name, column_type, **kwargs):
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
    ), {'t': table, 'c': column_name}).fetchone()
    if not result:
        op.add_column(table, sa.Column(column_name, column_type, **kwargs))


def upgrade():
    if not _table_exists('rind_arzneimittel_anwendung'):
        return
    _add_column_if_not_exists('rind_arzneimittel_anwendung', 'signatur_data', sa.Text(), nullable=True)
    _add_column_if_not_exists('rind_arzneimittel_anwendung', 'signatur_datum', sa.DateTime(), nullable=True)
    _add_column_if_not_exists('rind_arzneimittel_anwendung', 'signatur_name', sa.String(200), nullable=True)


def downgrade():
    with op.batch_alter_table('rind_arzneimittel_anwendung') as batch_op:
        batch_op.drop_column('signatur_name')
        batch_op.drop_column('signatur_datum')
        batch_op.drop_column('signatur_data')
