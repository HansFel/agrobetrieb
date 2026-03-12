"""
Backup-Service für AgroBetrieb.
Unterstützt SQLite (lokale Entwicklung) und PostgreSQL (Server/Docker).
"""
import gzip
import hashlib
import os
import shutil
import subprocess
import time
from datetime import datetime
from urllib.parse import urlparse

from flask import current_app
from app.extensions import db
from app.models.backup import Backup


BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    return BACKUP_DIR


def _db_type():
    """Erkennt ob SQLite oder PostgreSQL genutzt wird."""
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if uri.startswith('sqlite'):
        return 'sqlite'
    elif 'postgresql' in uri or 'postgres' in uri:
        return 'postgresql'
    return 'unknown'


def _parse_pg_uri():
    """Parsed PostgreSQL URI in Einzelteile."""
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    parsed = urlparse(uri)
    return {
        'host': parsed.hostname or 'localhost',
        'port': str(parsed.port or 5432),
        'user': parsed.username,
        'password': parsed.password,
        'dbname': parsed.path.lstrip('/'),
    }


def _sha256(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def backup_erstellen(user_id=None, typ='manuell'):
    """
    Erstellt ein Backup der Datenbank.
    Gibt das Backup-Objekt zurück oder wirft eine Exception.
    """
    _ensure_backup_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    db_engine = _db_type()
    start = time.time()

    if db_engine == 'sqlite':
        dateiname = f'backup_{timestamp}.db.gz'
        dateipfad = os.path.join(BACKUP_DIR, dateiname)
        _backup_sqlite(dateipfad)
    elif db_engine == 'postgresql':
        dateiname = f'backup_{timestamp}.sql.gz'
        dateipfad = os.path.join(BACKUP_DIR, dateiname)
        _backup_postgresql(dateipfad)
    else:
        raise RuntimeError(f'Unbekannter DB-Typ: {db_engine}')

    dauer = time.time() - start
    dateigroesse = os.path.getsize(dateipfad)
    checksum = _sha256(dateipfad)

    backup = Backup(
        dateiname=dateiname,
        dateipfad=dateipfad,
        dateigroesse=dateigroesse,
        checksum=checksum,
        typ=typ,
        status='erfolgreich',
        erstellt_von=user_id,
        dauer_sekunden=round(dauer, 2),
    )
    db.session.add(backup)
    db.session.commit()
    return backup


def _backup_sqlite(dateipfad):
    """Kopiert die SQLite-Datei und komprimiert sie."""
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    # sqlite:///relative.db oder sqlite:////absolute.db
    if uri.startswith('sqlite:////'):
        db_path = uri[len('sqlite:////'):]
    elif uri.startswith('sqlite:///'):
        db_path = uri[len('sqlite:///'):]
        if not os.path.isabs(db_path):
            db_path = os.path.join(current_app.instance_path, db_path)
    else:
        raise RuntimeError(f'Kann SQLite-Pfad nicht parsen: {uri}')

    if not os.path.exists(db_path):
        raise FileNotFoundError(f'SQLite-Datei nicht gefunden: {db_path}')

    with open(db_path, 'rb') as f_in:
        with gzip.open(dateipfad, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)


def _backup_postgresql(dateipfad):
    """Führt pg_dump aus und komprimiert die Ausgabe."""
    pg = _parse_pg_uri()
    env = os.environ.copy()
    env['PGPASSWORD'] = pg['password']

    cmd = [
        'pg_dump',
        '-h', pg['host'],
        '-p', pg['port'],
        '-U', pg['user'],
        '-d', pg['dbname'],
        '--no-owner',
        '--no-acl',
    ]

    proc = subprocess.run(
        cmd, env=env, capture_output=True, timeout=300
    )
    if proc.returncode != 0:
        raise RuntimeError(f'pg_dump fehlgeschlagen: {proc.stderr.decode("utf-8", errors="replace")}')

    with gzip.open(dateipfad, 'wb') as f:
        f.write(proc.stdout)


def backup_wiederherstellen(backup_id):
    """
    Stellt ein Backup wieder her.
    ACHTUNG: Überschreibt die aktuelle Datenbank!
    """
    backup = Backup.query.get_or_404(backup_id)

    if not os.path.exists(backup.dateipfad):
        raise FileNotFoundError(f'Backup-Datei nicht gefunden: {backup.dateipfad}')

    # Checksum prüfen
    aktueller_hash = _sha256(backup.dateipfad)
    if backup.checksum and aktueller_hash != backup.checksum:
        raise RuntimeError('Checksum stimmt nicht überein - Datei könnte beschädigt sein!')

    db_engine = _db_type()

    if db_engine == 'sqlite':
        _restore_sqlite(backup.dateipfad)
    elif db_engine == 'postgresql':
        _restore_postgresql(backup.dateipfad)
    else:
        raise RuntimeError(f'Unbekannter DB-Typ: {db_engine}')


def _restore_sqlite(dateipfad):
    """Stellt SQLite-Backup wieder her."""
    uri = current_app.config['SQLALCHEMY_DATABASE_URI']
    if uri.startswith('sqlite:////'):
        db_path = uri[len('sqlite:////'):]
    elif uri.startswith('sqlite:///'):
        db_path = uri[len('sqlite:///'):]
        if not os.path.isabs(db_path):
            db_path = os.path.join(current_app.instance_path, db_path)
    else:
        raise RuntimeError(f'Kann SQLite-Pfad nicht parsen: {uri}')

    # Alle Sessions schließen
    db.session.remove()
    db.engine.dispose()

    with gzip.open(dateipfad, 'rb') as f_in:
        with open(db_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)


def _restore_postgresql(dateipfad):
    """Stellt PostgreSQL-Backup wieder her."""
    pg = _parse_pg_uri()
    env = os.environ.copy()
    env['PGPASSWORD'] = pg['password']

    # SQL aus gzip lesen
    with gzip.open(dateipfad, 'rb') as f:
        sql_data = f.read()

    # Alle Sessions schließen
    db.session.remove()
    db.engine.dispose()

    cmd = [
        'psql',
        '-h', pg['host'],
        '-p', pg['port'],
        '-U', pg['user'],
        '-d', pg['dbname'],
    ]

    proc = subprocess.run(
        cmd, input=sql_data, env=env, capture_output=True, timeout=300
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode('utf-8', errors='replace')
        # Ignoriere "already exists"-Warnungen
        if 'ERROR' in stderr and 'already exists' not in stderr:
            raise RuntimeError(f'psql Restore fehlgeschlagen: {stderr}')


def backup_loeschen(backup_id):
    """Löscht ein Backup (Datei + DB-Eintrag)."""
    backup = Backup.query.get_or_404(backup_id)
    if os.path.exists(backup.dateipfad):
        os.remove(backup.dateipfad)
    db.session.delete(backup)
    db.session.commit()


def backup_liste():
    """Gibt alle Backups zurück, neueste zuerst."""
    return Backup.query.order_by(Backup.erstellt_am.desc()).all()
