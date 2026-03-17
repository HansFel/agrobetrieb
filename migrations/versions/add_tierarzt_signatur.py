"""Add signatur fields to tierarzt_besuch

Revision ID: add_tierarzt_signatur
Revises: 6dbb8fee6795
Create Date: 2026-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'add_tierarzt_signatur'
down_revision = '6dbb8fee6795'
branch_labels = None
depends_on = None


def _add_column_if_not_exists(table, column_name, column_type, **kwargs):
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c"
    ), {'t': table, 'c': column_name}).fetchone()
    if not result:
        op.add_column(table, sa.Column(column_name, column_type, **kwargs))


def upgrade():
    conn = op.get_bind()
    if not conn.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'tierarzt_besuch'"
    )).fetchone():
        return
    _add_column_if_not_exists('tierarzt_besuch', 'signatur_data', sa.Text(), nullable=True)
    _add_column_if_not_exists('tierarzt_besuch', 'signatur_datum', sa.DateTime(), nullable=True)
    _add_column_if_not_exists('tierarzt_besuch', 'signatur_name', sa.String(200), nullable=True)


def downgrade():
    with op.batch_alter_table('tierarzt_besuch') as batch_op:
        batch_op.drop_column('signatur_name')
        batch_op.drop_column('signatur_datum')
        batch_op.drop_column('signatur_data')
