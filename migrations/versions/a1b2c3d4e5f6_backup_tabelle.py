"""Backup-Tabelle für Datensicherung

Revision ID: a1b2c3d4e5f6
Revises: 49f21319ac9f
Create Date: 2026-03-12 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '49f21319ac9f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('backup',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('dateiname', sa.Text(), nullable=False),
        sa.Column('dateipfad', sa.Text(), nullable=False),
        sa.Column('dateigroesse', sa.BigInteger(), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('typ', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('fehler_meldung', sa.Text(), nullable=True),
        sa.Column('erstellt_von', sa.Integer(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.Column('dauer_sekunden', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['erstellt_von'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('backup')
