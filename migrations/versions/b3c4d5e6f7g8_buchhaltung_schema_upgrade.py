"""Buchhaltung Schema-Upgrade: Konto, Buchung, Kunde an neue Models anpassen

Revision ID: b3c4d5e6f7g8
Revises: a1b2c3d4e5f6
Create Date: 2026-03-12

"""
from alembic import op
import sqlalchemy as sa


revision = 'b3c4d5e6f7g8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # ============================================================
    # KONTO: nummer → kontonummer, typ → kontenklasse + kontotyp
    # ============================================================
    
    # Spalte 'nummer' umbenennen zu 'kontonummer'
    op.alter_column('konto', 'nummer', new_column_name='kontonummer', type_=sa.Text())
    
    # Bestehende 'typ'-Spalte in 'kontotyp' umbenennen
    op.alter_column('konto', 'typ', new_column_name='kontotyp', type_=sa.Text())
    
    # Neue Spalten hinzufügen
    op.add_column('konto', sa.Column('kontenklasse', sa.Integer(), nullable=True))
    op.add_column('konto', sa.Column('maschine_id', sa.Integer(), nullable=True))
    op.add_column('konto', sa.Column('jahresuebertrag', sa.Boolean(), server_default='false'))
    op.add_column('konto', sa.Column('ist_sammelkonto', sa.Boolean(), server_default='false'))
    op.add_column('konto', sa.Column('ist_importkonto', sa.Boolean(), server_default='false'))
    op.add_column('konto', sa.Column('aktiv', sa.Boolean(), server_default='true'))
    
    # Kontenklasse aus Kontonummer ableiten (erste Ziffer)
    op.execute("""
        UPDATE konto SET kontenklasse = CASE
            WHEN kontonummer ~ '^[0-9]' THEN CAST(LEFT(kontonummer, 1) AS INTEGER)
            ELSE 0
        END
    """)
    op.alter_column('konto', 'kontenklasse', nullable=False)
    
    # aktiv auf true setzen
    op.execute("UPDATE konto SET aktiv = true")
    
    # FK zu maschine
    op.create_foreign_key('fk_konto_maschine', 'konto', 'maschine', ['maschine_id'], ['id'])
    
    # ============================================================
    # BUCHUNG: Schema-Upgrade
    # ============================================================
    
    # Neue Spalten
    op.add_column('buchung', sa.Column('geschaeftsjahr', sa.Integer(), nullable=True))
    op.add_column('buchung', sa.Column('buchungsnummer', sa.Text(), nullable=True))
    op.add_column('buchung', sa.Column('buchungstext', sa.Text(), nullable=True))
    op.add_column('buchung', sa.Column('beleg_datum', sa.Date(), nullable=True))
    op.add_column('buchung', sa.Column('buchungsart', sa.Text(), server_default='manuell'))
    op.add_column('buchung', sa.Column('sammel_id', sa.Integer(), nullable=True))
    op.add_column('buchung', sa.Column('einsatz_id', sa.Integer(), nullable=True))
    op.add_column('buchung', sa.Column('bank_transaktion_id', sa.Integer(), nullable=True))
    op.add_column('buchung', sa.Column('storniert', sa.Boolean(), server_default='false'))
    op.add_column('buchung', sa.Column('storniert_am', sa.DateTime(), nullable=True))
    op.add_column('buchung', sa.Column('storniert_von', sa.Integer(), nullable=True))
    
    # Daten migrieren: beschreibung → buchungstext
    op.execute("UPDATE buchung SET buchungstext = beschreibung WHERE beschreibung IS NOT NULL")
    op.execute("UPDATE buchung SET buchungstext = '-' WHERE buchungstext IS NULL")
    
    # geschaeftsjahr aus datum ableiten
    op.execute("UPDATE buchung SET geschaeftsjahr = EXTRACT(YEAR FROM datum)")
    op.alter_column('buchung', 'geschaeftsjahr', nullable=False)
    
    # buchungsnummer generieren
    op.execute("""
        UPDATE buchung SET buchungsnummer = 
            geschaeftsjahr::text || '-' || LPAD(id::text, 3, '0')
    """)
    op.alter_column('buchung', 'buchungsnummer', nullable=False)
    op.alter_column('buchung', 'buchungstext', nullable=False)
    
    # erstellt_von_id → erstellt_von
    op.alter_column('buchung', 'erstellt_von_id', new_column_name='erstellt_von')
    
    # FK für storniert_von
    op.create_foreign_key('fk_buchung_storniert_von', 'buchung', 'user', ['storniert_von'], ['id'])
    
    # Unique constraint
    op.create_unique_constraint('uq_buchung_nummer', 'buchung', ['geschaeftsjahr', 'buchungsnummer'])
    
    # Alte Spalten entfernen
    op.drop_constraint('buchung_kategorie_id_fkey', 'buchung', type_='foreignkey')
    op.drop_column('buchung', 'kategorie_id')
    op.drop_column('buchung', 'beschreibung')
    op.drop_column('buchung', 'mwst_satz')
    op.drop_column('buchung', 'mwst_betrag')
    op.drop_column('buchung', 'bezahlt')
    
    # beleg_nummer Typ anpassen
    op.alter_column('buchung', 'beleg_nummer', type_=sa.Text())
    
    # ============================================================
    # KUNDE: Schema an neues Model anpassen
    # ============================================================
    
    # Neue Spalten
    op.add_column('kunde', sa.Column('adresse', sa.Text(), nullable=True))
    op.add_column('kunde', sa.Column('notizen', sa.Text(), nullable=True))
    op.add_column('kunde', sa.Column('iban', sa.Text(), nullable=True))
    op.add_column('kunde', sa.Column('aktiv', sa.Boolean(), server_default='true'))
    op.add_column('kunde', sa.Column('konto_id', sa.Integer(), nullable=True))
    
    # Daten migrieren: strasse → adresse
    op.execute("UPDATE kunde SET adresse = strasse WHERE strasse IS NOT NULL")
    op.execute("UPDATE kunde SET aktiv = true")
    
    # name Typ anpassen
    op.alter_column('kunde', 'name', type_=sa.Text())
    op.alter_column('kunde', 'plz', type_=sa.Text())
    op.alter_column('kunde', 'ort', type_=sa.Text())
    op.alter_column('kunde', 'email', type_=sa.Text())
    op.alter_column('kunde', 'telefon', type_=sa.Text())
    op.alter_column('kunde', 'uid_nummer', type_=sa.Text())
    
    # FK
    op.create_foreign_key('fk_kunde_konto', 'kunde', 'konto', ['konto_id'], ['id'], ondelete='SET NULL')
    
    # Alte Spalten entfernen
    op.drop_column('kunde', 'strasse')
    op.drop_column('kunde', 'land')
    op.drop_column('kunde', 'kontakt')
    op.drop_column('kunde', 'beschreibung')


def downgrade():
    # Buchung: Spalten zurück
    op.add_column('buchung', sa.Column('beschreibung', sa.Text(), nullable=True))
    op.execute("UPDATE buchung SET beschreibung = buchungstext")
    op.alter_column('buchung', 'beschreibung', nullable=False)
    op.add_column('buchung', sa.Column('kategorie_id', sa.Integer(), nullable=True))
    op.add_column('buchung', sa.Column('mwst_satz', sa.Numeric(5, 2), nullable=True))
    op.add_column('buchung', sa.Column('mwst_betrag', sa.Numeric(12, 2), nullable=True))
    op.add_column('buchung', sa.Column('bezahlt', sa.Boolean(), nullable=True))
    op.create_foreign_key('buchung_kategorie_id_fkey', 'buchung', 'kategorie', ['kategorie_id'], ['id'])
    op.alter_column('buchung', 'erstellt_von', new_column_name='erstellt_von_id')
    op.drop_constraint('uq_buchung_nummer', 'buchung', type_='unique')
    op.drop_constraint('fk_buchung_storniert_von', 'buchung', type_='foreignkey')
    op.drop_column('buchung', 'storniert_von')
    op.drop_column('buchung', 'storniert_am')
    op.drop_column('buchung', 'storniert')
    op.drop_column('buchung', 'bank_transaktion_id')
    op.drop_column('buchung', 'einsatz_id')
    op.drop_column('buchung', 'sammel_id')
    op.drop_column('buchung', 'buchungsart')
    op.drop_column('buchung', 'beleg_datum')
    op.drop_column('buchung', 'buchungstext')
    op.drop_column('buchung', 'buchungsnummer')
    op.drop_column('buchung', 'geschaeftsjahr')
    op.alter_column('buchung', 'beleg_nummer', type_=sa.String(50))
    
    # Konto: Spalten zurück
    op.alter_column('konto', 'kontonummer', new_column_name='nummer', type_=sa.String(20))
    op.alter_column('konto', 'kontotyp', new_column_name='typ', type_=sa.String(20))
    op.drop_constraint('fk_konto_maschine', 'konto', type_='foreignkey')
    op.drop_column('konto', 'aktiv')
    op.drop_column('konto', 'ist_importkonto')
    op.drop_column('konto', 'ist_sammelkonto')
    op.drop_column('konto', 'jahresuebertrag')
    op.drop_column('konto', 'maschine_id')
    op.drop_column('konto', 'kontenklasse')
    
    # Kunde: Spalten zurück
    op.add_column('kunde', sa.Column('strasse', sa.String(255), nullable=True))
    op.add_column('kunde', sa.Column('land', sa.String(2), nullable=True))
    op.add_column('kunde', sa.Column('kontakt', sa.String(255), nullable=True))
    op.add_column('kunde', sa.Column('beschreibung', sa.Text(), nullable=True))
    op.execute("UPDATE kunde SET strasse = adresse")
    op.drop_constraint('fk_kunde_konto', 'kunde', type_='foreignkey')
    op.drop_column('kunde', 'konto_id')
    op.drop_column('kunde', 'aktiv')
    op.drop_column('kunde', 'iban')
    op.drop_column('kunde', 'notizen')
    op.drop_column('kunde', 'adresse')
    op.alter_column('kunde', 'name', type_=sa.String(255))
    op.alter_column('kunde', 'plz', type_=sa.String(10))
    op.alter_column('kunde', 'ort', type_=sa.String(120))
    op.alter_column('kunde', 'email', type_=sa.String(120))
    op.alter_column('kunde', 'telefon', type_=sa.String(20))
    op.alter_column('kunde', 'uid_nummer', type_=sa.String(20))
