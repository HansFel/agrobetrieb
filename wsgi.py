#!/usr/bin/env python
"""
WSGI Entry Point für AgroBetrieb.
Wird von Gunicorn aufgerufen: gunicorn --bind 0.0.0.0:5000 wsgi:app

Führt automatisch aus:
1. Flask-Migrate (Alembic) Upgrading
2. Admin-Benutzer-Erstellung beim ersten Start
"""
import os
import sys
import logging
from time import sleep
from app import create_app, db
from app.models.user import User

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
)
logger = logging.getLogger(__name__)

# App-Instance außerhalb von create_app für Gunicorn
app = None
MAX_RETRIES = 30
RETRY_DELAY = 2

def initialize_app():
    """Initialisiert die Flask-App mit Migrations und Admin-Benutzer."""
    global app
    
    logger.info("🔧 AgroBetrieb Initialization startet...")
    
    # 1. App erstellen mit Error-Handling
    for attempt in range(MAX_RETRIES):
        try:
            app = create_app(os.getenv('FLASK_ENV', 'production'))
            logger.info(f"✅ App erstellt (Versuch {attempt + 1})")
            break
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                logger.warning(f"⚠️  App-Erstellen fehlgeschlagen: {e}. Versuche erneut in {RETRY_DELAY}s...")
                sleep(RETRY_DELAY)
            else:
                logger.error(f"❌ App-Erstellen nach {MAX_RETRIES} Versuchen fehlgeschlagen!")
                sys.exit(1)
    
    # 2. Datenbankverbindung warten
    with app.app_context():
        for attempt in range(MAX_RETRIES):
            try:
                # Test der Datenbankverbindung
                db.session.execute("SELECT 1")
                db.session.commit()
                logger.info(f"✅ Datenbank verbunden (Versuch {attempt + 1})")
                break
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"⚠️  DB-Verbindung fehlgeschlagen: {e}. Versuche in {RETRY_DELAY}s...")
                    sleep(RETRY_DELAY)
                else:
                    logger.error(f"❌ DB-Verbindung nach {MAX_RETRIES} Versuchen fehlgeschlagen!")
                    sys.exit(1)
        
        # 3. Migrations ausführen
        try:
            from flask_migrate import upgrade
            logger.info("🔄 Führe Flask-Migrate Upgrades aus...")
            try:
                upgrade()
                logger.info("✅ Flask-Migrate Upgrades abgeschlossen")
            except Exception as migrate_error:
                # Ignoriere Fehler wenn Tabelle bereits existiert
                if "already exists" in str(migrate_error) or "UNIQUE constraint failed" in str(migrate_error):
                    logger.warning(f"⚠️  Migrations bereits vorhanden, überspringe: {migrate_error}")
                else:
                    raise
        except Exception as e:
            logger.error(f"❌ Migration fehlgeschlagen: {e}")
            # Nicht kritisch - app läuft trotzdem weiter
        
        # 4. Admin-Benutzer erstellen (nur beim ersten Start)
        try:
            user_count = User.query.count()
            if user_count == 0:
                logger.info("📝 Erstelle Standard-Admin-Benutzer...")
                admin = User(
                    username='admin',
                    email='admin@agro.de',
                    vorname='Administrator',
                    nachname='System',
                    rolle='betriebsadmin',
                    aktiv=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                logger.info("✅ Admin-Benutzer erstellt (admin / admin123)")
            else:
                logger.info(f"✅ {user_count} Benutzer vorhanden, überspringe Admin-Erstellung")
        except Exception as e:
            logger.error(f"⚠️  Admin-Erstellung fehlgeschlagen: {e}")
            # Nicht kritisch - App läuft trotzdem
    
    logger.info("✨ AgroBetrieb Initialization abgeschlossen!")
    return app

# Initialisierung beim Start
if not app:
    app = initialize_app()
