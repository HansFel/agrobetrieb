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


def _is_pg(conn):
    return conn.dialect.name == 'postgresql'


def _alter_table(table, cols, renames, adds, drops, conn):
    """Dual-Dialekt ALTER TABLE: PostgreSQL direkt, SQLite via batch."""
    if _is_pg(conn):
        for old_name, new_name, type_ in renames:
            if old_name in cols and new_name not in cols:
                op.execute(sa.text(
                    f'ALTER TABLE {table} RENAME COLUMN {old_name} TO {new_name}'
                ))
                if type_ is not None:
                    type_str = 'TEXT' if isinstance(type_, sa.Text) else str(type_)
                    op.execute(sa.text(
                        f'ALTER TABLE {table} ALTER COLUMN {new_name} TYPE {type_str}'
                    ))
        for col in adds:
            if col.name not in cols:
                op.add_column(table, col)
        for col_name in drops:
            if col_name in cols:
                op.drop_column(table, col_name)
    else:
        with op.batch_alter_table(table, recreate='always') as batch_op:
            for old_name, new_name, type_ in renames:
                if old_name in cols and new_name not in cols:
                    batch_op.alter_column(old_name, new_column_name=new_name,
                                          type_=type_ if type_ else None)
            for col in adds:
                if col.name not in cols:
                    batch_op.add_column(col)
            for col_name in drops:
                if col_name in cols:
                    batch_op.drop_column(col_name)


def upgrade():
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    pg = _is_pg(conn)

    # ============================================================
    # KONTO: nummer → kontonummer, typ → kontotyp + neue Spalten
    # ============================================================
    if 'konto' in inspector.get_table_names():
        konto_cols = [c['name'] for c in inspector.get_columns('konto')]
        # Nur ausführen, wenn konto_cols gesetzt wurde

    # Entfernt: _alter_table('konto', ...) außerhalb des if-Blocks

    # Alle SQL-Operationen auf konto nur ausführen, wenn die Tabelle und Spalte existiert
    if 'konto' in inspector.get_table_names():
        konto_cols_check = [c['name'] for c in inspector.get_columns('konto')]
        # Kontenklasse aus Kontonummer ableiten (nur wenn Spalte existiert)
        if 'kontenklasse' in konto_cols_check:
            if pg:
                op.execute(sa.text("""
                    UPDATE konto SET kontenklasse = CAST(SUBSTRING(kontonummer FROM 1 FOR 1) AS INTEGER)
                    WHERE kontenklasse IS NULL AND kontonummer ~ '^[0-9]'
                """))
            else:
                op.execute("""
                    UPDATE konto SET kontenklasse = CAST(SUBSTR(kontonummer, 1, 1) AS INTEGER)
                    WHERE kontenklasse IS NULL AND kontonummer GLOB '[0-9]*'
                """)
            op.execute(sa.text("UPDATE konto SET kontenklasse = 0 WHERE kontenklasse IS NULL"))
        if 'aktiv' in konto_cols_check:
            op.execute(sa.text("UPDATE konto SET aktiv = true WHERE aktiv IS NULL") if pg else
                       "UPDATE konto SET aktiv = 1 WHERE aktiv IS NULL")

    # ============================================================
    # BUCHUNG: Schema-Upgrade
    # ============================================================
    buchung_cols = [c['name'] for c in inspector.get_columns('buchung')]

    _alter_table('buchung', buchung_cols,
        renames=[
            ('erstellt_von_id', 'erstellt_von', None),
        ],
        adds=[
            sa.Column('geschaeftsjahr', sa.Integer(), nullable=True),
            sa.Column('buchungsnummer', sa.Text(), nullable=True),
            sa.Column('buchungstext', sa.Text(), nullable=True),
            sa.Column('beleg_datum', sa.Date(), nullable=True),
            sa.Column('buchungsart', sa.Text(), server_default='manuell'),
            sa.Column('sammel_id', sa.Integer(), nullable=True),
            sa.Column('einsatz_id', sa.Integer(), nullable=True),
            sa.Column('bank_transaktion_id', sa.Integer(), nullable=True),
            sa.Column('storniert', sa.Boolean(), server_default='0'),
            sa.Column('storniert_am', sa.DateTime(), nullable=True),
            sa.Column('storniert_von', sa.Integer(), nullable=True),
        ],
        drops=['beschreibung', 'kategorie_id', 'mwst_satz', 'mwst_betrag', 'bezahlt'],
        conn=conn,
    )

    # Daten befüllen
    op.execute(sa.text("UPDATE buchung SET buchungstext = '-' WHERE buchungstext IS NULL"))
    if pg:
        op.execute(sa.text(
            "UPDATE buchung SET geschaeftsjahr = EXTRACT(YEAR FROM datum)::integer "
            "WHERE geschaeftsjahr IS NULL"
        ))
        op.execute(sa.text(
            "UPDATE buchung SET buchungsnummer = "
            "CAST(geschaeftsjahr AS TEXT) || '-' || LPAD(CAST(id AS TEXT), 4, '0') "
            "WHERE buchungsnummer IS NULL"
        ))
    else:
        op.execute(
            "UPDATE buchung SET geschaeftsjahr = CAST(STRFTIME('%Y', datum) AS INTEGER) "
            "WHERE geschaeftsjahr IS NULL"
        )
        op.execute(
            "UPDATE buchung SET buchungsnummer = "
            "CAST(geschaeftsjahr AS TEXT) || '-' || PRINTF('%04d', id) "
            "WHERE buchungsnummer IS NULL"
        )
    op.execute(sa.text("UPDATE buchung SET storniert = false WHERE storniert IS NULL") if pg else
               "UPDATE buchung SET storniert = 0 WHERE storniert IS NULL")

    # ============================================================
    # KUNDE: Schema an neues Model anpassen
    # ============================================================
    kunde_cols = [c['name'] for c in inspector.get_columns('kunde')]

    _alter_table('kunde', kunde_cols,
        renames=[],
        adds=[
            sa.Column('adresse', sa.Text(), nullable=True),
            sa.Column('notizen', sa.Text(), nullable=True),
            sa.Column('iban', sa.Text(), nullable=True),
            sa.Column('aktiv', sa.Boolean(), server_default='1'),
            sa.Column('konto_id', sa.Integer(), nullable=True),
        ],
        drops=['strasse', 'land', 'kontakt', 'beschreibung'],
        conn=conn,
    )

    op.execute(sa.text("UPDATE kunde SET aktiv = true WHERE aktiv IS NULL") if pg else
               "UPDATE kunde SET aktiv = 1 WHERE aktiv IS NULL")


def downgrade():
    conn = op.get_bind()
    pg = _is_pg(conn)

    if pg:
        op.add_column('buchung', sa.Column('beschreibung', sa.Text(), nullable=True))
        op.add_column('buchung', sa.Column('kategorie_id', sa.Integer(), nullable=True))
        op.add_column('buchung', sa.Column('mwst_satz', sa.Numeric(5, 2), nullable=True))
        op.add_column('buchung', sa.Column('mwst_betrag', sa.Numeric(12, 2), nullable=True))
        op.add_column('buchung', sa.Column('bezahlt', sa.Boolean(), nullable=True))
        for col in ('storniert_von', 'storniert_am', 'storniert',
                     'bank_transaktion_id', 'einsatz_id', 'sammel_id',
                     'buchungsart', 'beleg_datum', 'buchungstext'):
            op.drop_column('buchung', col)
    else:
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
