"""
WSGI Entry Point fuer AgroBetrieb.
Migrationen und Admin-Erstellung laufen ueber entrypoint.sh
BEVOR Gunicorn startet. Hier nur die App erstellen.
"""
import os
from app import create_app

flask_app = create_app(os.getenv('FLASK_ENV', 'production'))

# Automatische Backups starten (Daemon-Thread, nur einmal pro Prozess)
from app.services.backup_service import auto_backup_starten
auto_backup_starten(flask_app)

# Sub-Path-Deployment: APPLICATION_PREFIX=/agro1 → App unter /agro1 mounten
prefix = os.environ.get('APPLICATION_PREFIX', '').rstrip('/')
if prefix:
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from werkzeug.wrappers import Response

    flask_app.config['APPLICATION_ROOT'] = prefix
    flask_app.config['PREFERRED_URL_SCHEME'] = 'https'

    def _not_found(environ, start_response):
        res = Response('Not found', status=404)
        return res(environ, start_response)

    app = DispatcherMiddleware(_not_found, {prefix: flask_app})
else:
    app = flask_app
