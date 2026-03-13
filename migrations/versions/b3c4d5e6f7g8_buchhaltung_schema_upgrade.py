"""Buchhaltung Schema-Upgrade: Konto, Buchung, Kunde an neue Models anpassen

Revision ID: b3c4d5e6f7g8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


revision = 'b3c4d5e6f7g8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)

    # ============================================================
    # KONTO: nummer → kontonummer, typ → kontotyp + neue Spalten
    # ============================================================
    konto_cols = [c['name'] for c in inspector.get_columns('konto')]

    with op.batch_alter_table('konto', recreate='always') as batch_op:
        if 'nummer' in konto_cols:
            batch_op.alter_column('nummer', new_column_name='kontonummer', type_=sa.Text())
        if 'typ' in konto_cols:
            batch_op.alter_column('typ', new_column_name='kontotyp', type_=sa.Text())
        if 'kontenklasse' not in konto_cols:
            batch_op.add_column(sa.Column('kontenklasse', sa.Integer(), nullable=True))
        if 'maschine_id' not in konto_cols:
            batch_op.add_column(sa.Column('maschine_id', sa.Integer(), nullable=True))
        if 'jahresuebertrag' not in konto_cols:
            batch_op.add_column(sa.Column('jahresuebertrag', sa.Boolean(), server_default='0'))
        if 'ist_sammelkonto' not in konto_cols:
            batch_op.add_column(sa.Column('ist_sammelkonto', sa.Boolean(), server_default='0'))
        if 'ist_importkonto' not in konto_cols:
            batch_op.add_column(sa.Column('ist_importkonto', sa.Boolean(), server_default='0'))
        if 'aktiv' not in konto_cols:
            batch_op.add_column(sa.Column('aktiv', sa.Boolean(), server_default='1'))

    # Kontenklasse aus Kontonummer ableiten (SQLite-kompatibel)
    op.execute("""
        UPDATE konto SET kontenklasse = CAST(SUBSTR(kontonummer, 1, 1) AS INTEGER)
        WHERE kontenklasse IS NULL AND kontonummer GLOB '[0-9]*'
    """)
    op.execute("UPDATE konto SET kontenklasse = 0 WHERE kontenklasse IS NULL")
    op.execute("UPDATE konto SET aktiv = 1 WHERE aktiv IS NULL")

    # ============================================================
    # BUCHUNG: Schema-Upgrade
    # ============================================================
    buchung_cols = [c['name'] for c in inspector.get_columns('buchung')]

    with op.batch_alter_table('buchung', recreate='always') as batch_op:
        if 'geschaeftsjahr' not in buchung_cols:
            batch_op.add_column(sa.Column('geschaeftsjahr', sa.Integer(), nullable=True))
        if 'buchungsnummer' not in buchung_cols:
            batch_op.add_column(sa.Column('buchungsnummer', sa.Text(), nullable=True))
        if 'buchungstext' not in buchung_cols:
            batch_op.add_column(sa.Column('buchungstext', sa.Text(), nullable=True))
        if 'beleg_datum' not in buchung_cols:
            batch_op.add_column(sa.Column('beleg_datum', sa.Date(), nullable=True))
        if 'buchungsart' not in buchung_cols:
            batch_op.add_column(sa.Column('buchungsart', sa.Text(), server_default='manuell'))
        if 'sammel_id' not in buchung_cols:
            batch_op.add_column(sa.Column('sammel_id', sa.Integer(), nullable=True))
        if 'einsatz_id' not in buchung_cols:
            batch_op.add_column(sa.Column('einsatz_id', sa.Integer(), nullable=True))
        if 'bank_transaktion_id' not in buchung_cols:
            batch_op.add_column(sa.Column('bank_transaktion_id', sa.Integer(), nullable=True))
        if 'storniert' not in buchung_cols:
            batch_op.add_column(sa.Column('storniert', sa.Boolean(), server_default='0'))
        if 'storniert_am' not in buchung_cols:
            batch_op.add_column(sa.Column('storniert_am', sa.DateTime(), nullable=True))
        if 'storniert_von' not in buchung_cols:
            batch_op.add_column(sa.Column('storniert_von', sa.Integer(), nullable=True))
        # erstellt_von_id → erstellt_von umbenennen
        if 'erstellt_von_id' in buchung_cols and 'erstellt_von' not in buchung_cols:
            batch_op.alter_column('erstellt_von_id', new_column_name='erstellt_von')
        # Alte Spalten entfernen
        if 'beschreibung' in buchung_cols:
            batch_op.drop_column('beschreibung')
        if 'kategorie_id' in buchung_cols:
            batch_op.drop_column('kategorie_id')
        if 'mwst_satz' in buchung_cols:
            batch_op.drop_column('mwst_satz')
        if 'mwst_betrag' in buchung_cols:
            batch_op.drop_column('mwst_betrag')
        if 'bezahlt' in buchung_cols:
            batch_op.drop_column('bezahlt')

    # Daten befüllen (SQLite-kompatibel)
    op.execute("UPDATE buchung SET buchungstext = '-' WHERE buchungstext IS NULL")
    op.execute("UPDATE buchung SET geschaeftsjahr = CAST(STRFTIME('%Y', datum) AS INTEGER) WHERE geschaeftsjahr IS NULL")
    op.execute("""
        UPDATE buchung SET buchungsnummer =
            CAST(geschaeftsjahr AS TEXT) || '-' || PRINTF('%04d', id)
        WHERE buchungsnummer IS NULL
    """)
    op.execute("UPDATE buchung SET storniert = 0 WHERE storniert IS NULL")

    # ============================================================
    # KUNDE: Schema an neues Model anpassen
    # ============================================================
    kunde_cols = [c['name'] for c in inspector.get_columns('kunde')]

    with op.batch_alter_table('kunde', recreate='always') as batch_op:
        if 'adresse' not in kunde_cols:
            batch_op.add_column(sa.Column('adresse', sa.Text(), nullable=True))
        if 'notizen' not in kunde_cols:
            batch_op.add_column(sa.Column('notizen', sa.Text(), nullable=True))
        if 'iban' not in kunde_cols:
            batch_op.add_column(sa.Column('iban', sa.Text(), nullable=True))
        if 'aktiv' not in kunde_cols:
            batch_op.add_column(sa.Column('aktiv', sa.Boolean(), server_default='1'))
        if 'konto_id' not in kunde_cols:
            batch_op.add_column(sa.Column('konto_id', sa.Integer(), nullable=True))
        if 'strasse' in kunde_cols:
            batch_op.drop_column('strasse')
        if 'land' in kunde_cols:
            batch_op.drop_column('land')
        if 'kontakt' in kunde_cols:
            batch_op.drop_column('kontakt')
        if 'beschreibung' in kunde_cols:
            batch_op.drop_column('beschreibung')

    op.execute("UPDATE kunde SET aktiv = 1 WHERE aktiv IS NULL")


def downgrade():
    with op.batch_alter_table('buchung', recreate='always') as batch_op:
        batch_op.add_column(sa.Column('beschreibung', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('kategorie_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('mwst_satz', sa.Numeric(5, 2), nullable=True))
        batch_op.add_column(sa.Column('mwst_betrag', sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column('bezahlt', sa.Boolean(), nullable=True))
        batch_op.drop_column('storniert_von')
        batch_op.drop_column('storniert_am')
        batch_op.drop_column('storniert')
        batch_op.drop_column('bank_transaktion_id')
        batch_op.drop_column('einsatz_id')
        batch_op.drop_column('sammel_id')
        batch_op.drop_column('buchungsart')
        batch_op.drop_column('beleg_datum')
        batch_op.drop_column('buchungstext')
        batch_op.drop_column('buchungsnummer')
        batch_op.drop_column('geschaeftsjahr')
        batch_op.alter_column('erstellt_von', new_column_name='erstellt_von_id')

    with op.batch_alter_table('konto', recreate='always') as batch_op:
        batch_op.alter_column('kontonummer', new_column_name='nummer', type_=sa.String(20))
        batch_op.alter_column('kontotyp', new_column_name='typ', type_=sa.String(20))
        batch_op.drop_column('aktiv')
        batch_op.drop_column('ist_importkonto')
        batch_op.drop_column('ist_sammelkonto')
        batch_op.drop_column('jahresuebertrag')
        batch_op.drop_column('maschine_id')
        batch_op.drop_column('kontenklasse')

    with op.batch_alter_table('kunde', recreate='always') as batch_op:
        batch_op.add_column(sa.Column('strasse', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('land', sa.String(2), nullable=True))
        batch_op.add_column(sa.Column('kontakt', sa.String(255), nullable=True))
        batch_op.add_column(sa.Column('beschreibung', sa.Text(), nullable=True))
        batch_op.drop_column('konto_id')
        batch_op.drop_column('aktiv')
        batch_op.drop_column('iban')
        batch_op.drop_column('notizen')
        batch_op.drop_column('adresse')
