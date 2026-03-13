"""
WSGI Entry Point fuer AgroBetrieb.
Migrationen und Admin-Erstellung laufen ueber entrypoint.sh
BEVOR Gunicorn startet. Hier nur die App erstellen.
"""
import os
from app import create_app

app = create_app(os.getenv('FLASK_ENV', 'production'))

# Automatische Backups starten (Daemon-Thread, nur einmal pro Prozess)
from app.services.backup_service import auto_backup_starten
auto_backup_starten(app)
