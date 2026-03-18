"""Add externe_app and betrieb_externe_app tables

Revision ID: add_externe_apps
Revises: add_tamg_signatur_milchvieh
Create Date: 2026-03-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = 'add_externe_apps'
down_revision = 'add_tamg_signatur_milchvieh'
branch_labels = None
depends_on = None


def _table_exists(table_name):
    conn = op.get_bind()
    return conn.execute(text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
    ), {'t': table_name}).fetchone() is not None


def upgrade():
    if not _table_exists('externe_app'):
        op.create_table(
            'externe_app',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(100), nullable=False),
            sa.Column('kuerzel', sa.String(30), unique=True, nullable=False),
            sa.Column('basis_url', sa.String(255), nullable=False),
            sa.Column('icon', sa.String(50), server_default='bi-box-arrow-up-right'),
            sa.Column('beschreibung', sa.String(255), nullable=True),
            sa.Column('aktiv', sa.Boolean(), server_default='true', nullable=False),
            sa.Column('reihenfolge', sa.Integer(), server_default='0'),
        )
        op.create_index('ix_externe_app_kuerzel', 'externe_app', ['kuerzel'])

    if not _table_exists('betrieb_externe_app'):
        op.create_table(
            'betrieb_externe_app',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('betrieb_id', sa.Integer(),
                      sa.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False),
            sa.Column('app_id', sa.Integer(),
                      sa.ForeignKey('externe_app.id', ondelete='CASCADE'), nullable=False),
            sa.UniqueConstraint('betrieb_id', 'app_id', name='uq_betrieb_externe_app'),
        )
        op.create_index('ix_betrieb_externe_app_betrieb', 'betrieb_externe_app', ['betrieb_id'])


def downgrade():
    op.drop_index('ix_betrieb_externe_app_betrieb')
    op.drop_table('betrieb_externe_app')
    op.drop_index('ix_externe_app_kuerzel')
    op.drop_table('externe_app')
