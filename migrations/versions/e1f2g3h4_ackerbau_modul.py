"""Ackerbau-Modul: Schlagkartei, Spritztagebuch, Düngerplaner, Pro-Erweiterung

Revision ID: e1f2g3h4
Revises: merge_signatur_heads
Create Date: 2026-03-16
"""
from alembic import op
import sqlalchemy as sa

revision = 'e1f2g3h4'
down_revision = 'merge_signatur_heads'
branch_labels = None
depends_on = None


def upgrade():
    # Betrieb: zwei neue Modul-Flags
    op.add_column('betrieb', sa.Column('modul_ackerbau', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('betrieb', sa.Column('modul_ackerbau_pro', sa.Boolean(), nullable=False, server_default='false'))

    # Schlag
    op.create_table(
        'schlag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('betrieb_id', sa.Integer(), sa.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('flaeche_ha', sa.Numeric(10, 4), nullable=True),
        sa.Column('feldstueck_nr', sa.String(50), nullable=True),
        sa.Column('invekos_flaeche', sa.Numeric(10, 4), nullable=True),
        sa.Column('bodenart', sa.String(50), nullable=True),
        sa.Column('notizen', sa.Text(), nullable=True),
        sa.Column('aktiv', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schlag_betrieb_id', 'schlag', ['betrieb_id'])

    # SchlagKultur
    op.create_table(
        'schlag_kultur',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schlag_id', sa.Integer(), sa.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kultur_code', sa.String(20), nullable=False),
        sa.Column('kultur_name', sa.String(100), nullable=False),
        sa.Column('aussaat_datum', sa.Date(), nullable=False),
        sa.Column('ernte_datum', sa.Date(), nullable=True),
        sa.Column('bemerkungen', sa.Text(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_schlag_kultur_schlag_id', 'schlag_kultur', ['schlag_id'])

    # Spritzmittel
    op.create_table(
        'spritzmittel',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('betrieb_id', sa.Integer(), sa.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('wirkstoff', sa.String(200), nullable=True),
        sa.Column('zulassungsnummer', sa.String(50), nullable=True),
        sa.Column('registernummer', sa.String(50), nullable=True),
        sa.Column('kategorie', sa.String(50), nullable=True),
        sa.Column('einheit', sa.String(20), nullable=True, server_default='l/ha'),
        sa.Column('aktiv', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_spritzmittel_betrieb_id', 'spritzmittel', ['betrieb_id'])

    # Spritzung (Spritztagebuch)
    op.create_table(
        'spritzung',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schlag_id', sa.Integer(), sa.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('schlag_kultur_id', sa.Integer(), sa.ForeignKey('schlag_kultur.id', ondelete='SET NULL'), nullable=True),
        sa.Column('spritzmittel_id', sa.Integer(), sa.ForeignKey('spritzmittel.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('datum', sa.Date(), nullable=False),
        sa.Column('uhrzeit', sa.Time(), nullable=True),
        sa.Column('bbch_stadium', sa.String(10), nullable=True),
        sa.Column('aufwandmenge', sa.Numeric(10, 3), nullable=False),
        sa.Column('invekos_flaeche', sa.Numeric(10, 4), nullable=True),
        sa.Column('behandelte_flaeche', sa.Numeric(10, 4), nullable=True),
        sa.Column('bemerkungen', sa.Text(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_spritzung_schlag_id', 'spritzung', ['schlag_id'])
    op.create_index('ix_spritzung_datum', 'spritzung', ['datum'])

    # Düngung
    op.create_table(
        'duengung',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schlag_id', sa.Integer(), sa.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kultur_id', sa.Integer(), sa.ForeignKey('schlag_kultur.id', ondelete='SET NULL'), nullable=True),
        sa.Column('datum', sa.Date(), nullable=False),
        sa.Column('duenger_art', sa.String(50), nullable=False),
        sa.Column('duenger_name', sa.String(100), nullable=True),
        sa.Column('n_gehalt', sa.Numeric(8, 2), nullable=True),
        sa.Column('p_gehalt', sa.Numeric(8, 2), nullable=True),
        sa.Column('k_gehalt', sa.Numeric(8, 2), nullable=True),
        sa.Column('menge', sa.Numeric(10, 2), nullable=False),
        sa.Column('einheit', sa.String(20), nullable=True, server_default='kg/ha'),
        sa.Column('behandelte_flaeche', sa.Numeric(10, 2), nullable=True),
        sa.Column('n_ausgebracht', sa.Numeric(10, 2), nullable=True),
        sa.Column('p_ausgebracht', sa.Numeric(10, 2), nullable=True),
        sa.Column('k_ausgebracht', sa.Numeric(10, 2), nullable=True),
        sa.Column('ausbringverfahren', sa.String(50), nullable=True),
        sa.Column('einarbeitung', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('bemerkungen', sa.Text(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_duengung_schlag_id', 'duengung', ['schlag_id'])

    # Bodenuntersuchung (Pro)
    op.create_table(
        'bodenuntersuchung',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schlag_id', sa.Integer(), sa.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('datum', sa.Date(), nullable=False),
        sa.Column('labor', sa.String(100), nullable=True),
        sa.Column('ph_wert', sa.Numeric(4, 2), nullable=True),
        sa.Column('p_gehalt', sa.Numeric(8, 2), nullable=True),
        sa.Column('k_gehalt', sa.Numeric(8, 2), nullable=True),
        sa.Column('mg_gehalt', sa.Numeric(8, 2), nullable=True),
        sa.Column('humus', sa.Numeric(5, 2), nullable=True),
        sa.Column('p_klasse', sa.String(1), nullable=True),
        sa.Column('k_klasse', sa.String(1), nullable=True),
        sa.Column('mg_klasse', sa.String(1), nullable=True),
        sa.Column('bemerkungen', sa.Text(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Düngebedarfsermittlung (Pro)
    op.create_table(
        'duengebedarfsermittlung',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schlag_id', sa.Integer(), sa.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False),
        sa.Column('kultur_id', sa.Integer(), sa.ForeignKey('schlag_kultur.id', ondelete='SET NULL'), nullable=True),
        sa.Column('jahr', sa.Integer(), nullable=False),
        sa.Column('ertragsziel_dt_ha', sa.Numeric(8, 2), nullable=True),
        sa.Column('n_bedarf_brutto', sa.Numeric(8, 2), nullable=True),
        sa.Column('n_bedarf_netto', sa.Numeric(8, 2), nullable=True),
        sa.Column('n_nachlieferung_boden', sa.Numeric(8, 2), nullable=True),
        sa.Column('n_aus_vorfrucht', sa.Numeric(8, 2), nullable=True),
        sa.Column('n_aus_wirtschaft', sa.Numeric(8, 2), nullable=True),
        sa.Column('ist_rotes_gebiet', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('reduktion_rotes_gebiet', sa.Numeric(5, 2), nullable=True, server_default='20'),
        sa.Column('n_mineraldung_empfehlung', sa.Numeric(8, 2), nullable=True),
        sa.Column('kommentar', sa.Text(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # Tierbestand (Pro)
    op.create_table(
        'tierbestand',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('betrieb_id', sa.Integer(), sa.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False),
        sa.Column('jahr', sa.Integer(), nullable=False),
        sa.Column('tier_kategorie', sa.String(100), nullable=False),
        sa.Column('haltungsform', sa.String(50), nullable=True),
        sa.Column('anzahl', sa.Numeric(10, 2), nullable=False),
        sa.Column('n_anfall_jahr', sa.Numeric(10, 2), nullable=True),
        sa.Column('n_feldfallend', sa.Numeric(10, 2), nullable=True),
        sa.Column('bemerkungen', sa.Text(), nullable=True),
        sa.Column('erstellt_am', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('betrieb_id', 'jahr', 'tier_kategorie', 'haltungsform',
                            name='uq_tierbestand_betrieb_jahr_tier'),
    )


def downgrade():
    op.drop_table('tierbestand')
    op.drop_table('duengebedarfsermittlung')
    op.drop_table('bodenuntersuchung')
    op.drop_table('duengung')
    op.drop_index('ix_spritzung_datum', 'spritzung')
    op.drop_index('ix_spritzung_schlag_id', 'spritzung')
    op.drop_table('spritzung')
    op.drop_index('ix_spritzmittel_betrieb_id', 'spritzmittel')
    op.drop_table('spritzmittel')
    op.drop_index('ix_schlag_kultur_schlag_id', 'schlag_kultur')
    op.drop_table('schlag_kultur')
    op.drop_index('ix_schlag_betrieb_id', 'schlag')
    op.drop_table('schlag')
    op.drop_column('betrieb', 'modul_ackerbau_pro')
    op.drop_column('betrieb', 'modul_ackerbau')
