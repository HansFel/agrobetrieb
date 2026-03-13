"""
Backup-Service für AgroBetrieb.
Unterstützt SQLite (lokale Entwicklung) und PostgreSQL (Server/Docker).
Bietet automatische Backups, Aufbewahrungsrichtlinie und Pre-Restore-Sicherung.
"""
import gzip
import hashlib
import logging
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timedelta
from urllib.parse import urlparse

from flask import current_app
from app.extensions import db
from app.models.backup import Backup


BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'backups')

# Standard-Aufbewahrungsrichtlinie
DEFAULT_MAX_BACKUPS = 30           # Maximal 30 Backups behalten
DEFAULT_MAX_ALTER_TAGE = 90        # Backups älter als 90 Tage löschen
DEFAULT_AUTO_INTERVALL_H = 24      # Alle 24 Stunden automatisches Backup

logger = logging.getLogger(__name__)


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
    Erstellt vorher ein Sicherungs-Backup der aktuellen DB.
    ACHTUNG: Überschreibt die aktuelle Datenbank!
    """
    backup = Backup.query.get_or_404(backup_id)

    if not os.path.exists(backup.dateipfad):
        raise FileNotFoundError(f'Backup-Datei nicht gefunden: {backup.dateipfad}')

    # Checksum prüfen
    aktueller_hash = _sha256(backup.dateipfad)
    if backup.checksum and aktueller_hash != backup.checksum:
        raise RuntimeError('Checksum stimmt nicht überein - Datei könnte beschädigt sein!')

    # Sicherungs-Backup VOR der Wiederherstellung erstellen
    logger.info('Erstelle Pre-Restore-Backup der aktuellen Datenbank...')
    try:
        pre_backup = backup_erstellen(user_id=None, typ='pre-restore')
        logger.info('Pre-Restore-Backup erstellt: %s', pre_backup.dateiname)
    except Exception as e:
        logger.error('Pre-Restore-Backup fehlgeschlagen: %s', e)
        raise RuntimeError(f'Sicherungs-Backup vor Wiederherstellung fehlgeschlagen: {e}')

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


def aufbewahrung_aufraeumen(max_backups=DEFAULT_MAX_BACKUPS, max_alter_tage=DEFAULT_MAX_ALTER_TAGE):
    """
    Wendet die Aufbewahrungsrichtlinie an:
    - Löscht Backups die älter als max_alter_tage sind
    - Behält maximal max_backups (neueste zuerst, Pre-Restore nicht mitzählen)
    Gibt die Anzahl gelöschter Backups zurück.
    """
    geloescht = 0

    # 1. Alte Backups löschen
    if max_alter_tage > 0:
        grenze = datetime.utcnow() - timedelta(days=max_alter_tage)
        alte = Backup.query.filter(Backup.erstellt_am < grenze).all()
        for b in alte:
            if os.path.exists(b.dateipfad):
                os.remove(b.dateipfad)
            db.session.delete(b)
            geloescht += 1

    # 2. Überzählige Backups löschen (älteste zuerst)
    if max_backups > 0:
        alle = Backup.query.order_by(Backup.erstellt_am.desc()).all()
        if len(alle) > max_backups:
            ueberzaehlige = alle[max_backups:]
            for b in ueberzaehlige:
                if os.path.exists(b.dateipfad):
                    os.remove(b.dateipfad)
                db.session.delete(b)
                geloescht += 1

    if geloescht > 0:
        db.session.commit()
        logger.info('Aufbewahrung: %d Backups gelöscht', geloescht)

    return geloescht


def backup_statistik():
    """Gibt Statistiken über vorhandene Backups zurück."""
    backups = Backup.query.filter_by(status='erfolgreich').all()
    if not backups:
        return {
            'anzahl': 0,
            'gesamtgroesse': 0,
            'gesamtgroesse_formatiert': '0 B',
            'aeltestes': None,
            'neuestes': None,
            'naechstes_auto': None,
        }

    gesamt = sum(b.dateigroesse or 0 for b in backups)
    sortiert = sorted(backups, key=lambda b: b.erstellt_am)

    # Nächstes automatisches Backup
    letztes_auto = Backup.query.filter_by(typ='automatisch', status='erfolgreich') \
        .order_by(Backup.erstellt_am.desc()).first()
    naechstes = None
    if letztes_auto:
        naechstes = letztes_auto.erstellt_am + timedelta(hours=DEFAULT_AUTO_INTERVALL_H)

    return {
        'anzahl': len(backups),
        'gesamtgroesse': gesamt,
        'gesamtgroesse_formatiert': _format_groesse(gesamt),
        'aeltestes': sortiert[0].erstellt_am if sortiert else None,
        'neuestes': sortiert[-1].erstellt_am if sortiert else None,
        'naechstes_auto': naechstes,
        'max_backups': DEFAULT_MAX_BACKUPS,
        'max_alter_tage': DEFAULT_MAX_ALTER_TAGE,
        'auto_intervall_h': DEFAULT_AUTO_INTERVALL_H,
    }


def _format_groesse(size_bytes):
    """Formatiert Bytes in lesbare Größe."""
    if size_bytes < 1024:
        return f'{size_bytes} B'
    elif size_bytes < 1024 * 1024:
        return f'{size_bytes / 1024:.1f} KB'
    elif size_bytes < 1024 * 1024 * 1024:
        return f'{size_bytes / (1024 * 1024):.1f} MB'
    else:
        return f'{size_bytes / (1024 * 1024 * 1024):.2f} GB'


def backup_upload(datei, user_id=None):
    """
    Nimmt eine hochgeladene Backup-Datei (.sql.gz oder .db.gz) entgegen
    und registriert sie im System.
    """
    _ensure_backup_dir()

    if not datei or not datei.filename:
        raise ValueError('Keine Datei ausgewählt')

    original_name = datei.filename
    if not (original_name.endswith('.sql.gz') or original_name.endswith('.db.gz')):
        raise ValueError('Nur .sql.gz oder .db.gz Dateien erlaubt')

    # Sicherer Dateiname
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    ext = '.sql.gz' if original_name.endswith('.sql.gz') else '.db.gz'
    dateiname = f'upload_{timestamp}{ext}'
    dateipfad = os.path.join(BACKUP_DIR, dateiname)

    datei.save(dateipfad)

    dateigroesse = os.path.getsize(dateipfad)
    checksum = _sha256(dateipfad)

    backup = Backup(
        dateiname=dateiname,
        dateipfad=dateipfad,
        dateigroesse=dateigroesse,
        checksum=checksum,
        typ='upload',
        status='erfolgreich',
        erstellt_von=user_id,
        dauer_sekunden=0,
    )
    db.session.add(backup)
    db.session.commit()
    return backup


# --- Automatisches Backup ---

_auto_backup_thread = None


def auto_backup_starten(app):
    """Startet den automatischen Backup-Thread. Nur ein Worker übernimmt das via Lock-File."""
    global _auto_backup_thread
    if _auto_backup_thread is not None and _auto_backup_thread.is_alive():
        return

    _auto_backup_thread = threading.Thread(
        target=_auto_backup_loop,
        args=(app,),
        daemon=True,
        name='auto-backup'
    )
    _auto_backup_thread.start()
    logger.info('Automatischer Backup-Thread gestartet (Intervall: %dh)', DEFAULT_AUTO_INTERVALL_H)


def _auto_backup_loop(app):
    """Endlos-Loop für automatische Backups. Nutzt Lock-File damit nur ein Worker aktiv ist."""
    lock_path = os.path.join(BACKUP_DIR, '.auto_backup.lock')
    _ensure_backup_dir()

    lock_fd = None
    try:
        import fcntl
        lock_fd = open(lock_path, 'w')
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except ImportError:
        # Windows: kein fcntl, Thread läuft ohne Lock
        pass
    except (IOError, OSError):
        # Anderer Worker hat den Lock — dieser Thread beendet sich
        if lock_fd:
            lock_fd.close()
        logger.debug('Auto-Backup: Anderer Worker hat den Lock, überspringe')
        return

    try:
        while True:
            # Warte auf nächsten Durchlauf
            time.sleep(60)  # Erste Minute warten, dann prüfen

            with app.app_context():
                # Prüfe ob ein Backup fällig ist
                letztes = Backup.query.filter_by(status='erfolgreich') \
                    .order_by(Backup.erstellt_am.desc()).first()

                soll_backup = False
                if letztes is None:
                    soll_backup = True
                else:
                    alter_stunden = (datetime.utcnow() - letztes.erstellt_am).total_seconds() / 3600
                    if alter_stunden >= DEFAULT_AUTO_INTERVALL_H:
                        soll_backup = True

                if soll_backup:
                    logger.info('Automatisches Backup wird erstellt...')
                    try:
                        backup = backup_erstellen(user_id=None, typ='automatisch')
                        logger.info('Automatisches Backup erstellt: %s (%s)',
                                    backup.dateiname, backup.groesse_formatiert)
                        # Aufräumen nach automatischem Backup
                        aufbewahrung_aufraeumen()
                    except Exception as e:
                        logger.error('Automatisches Backup fehlgeschlagen: %s', e)

            # Nächste Prüfung in 1 Stunde
            time.sleep(3600)
    finally:
        if lock_fd:
            try:
                import fcntl
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except ImportError:
                pass
            lock_fd.close()
