#!/bin/bash
set -e

echo "=== AgroBetrieb Startup ==="

# Build-Hash setzen (aus BUILD_HASH-Datei wenn Env-Variable nicht gesetzt)
if [ "${COMMIT_HASH:-unknown}" = "unknown" ] && [ -f /app/BUILD_HASH ]; then
    export COMMIT_HASH=$(cat /app/BUILD_HASH)
fi
echo "Build: ${COMMIT_HASH:-unknown}"

# 1. Warte auf Datenbank
echo "Warte auf Datenbank..."
# DB-Host aus DATABASE_URL extrahieren oder Fallback auf Env-Variable / Default
if [ -n "${DB_HOST}" ]; then
    _DB_HOST="${DB_HOST}"
elif [ -n "${DATABASE_URL}" ]; then
    _DB_HOST=$(echo "${DATABASE_URL}" | sed -E 's|.*@([^:/]+).*|\1|')
else
    _DB_HOST="agrobetrieb-db"
fi
_DB_USER=$(echo "${DATABASE_URL}" | sed -E 's|.*://([^:]+):.*|\1|' 2>/dev/null || echo "agr_user")
echo "  DB-Host: ${_DB_HOST}"
until pg_isready -h "${_DB_HOST}" -p 5432 -U "${_DB_USER}" -q; do
    echo "  DB noch nicht bereit, warte 2s..."
    sleep 2
done
echo "DB bereit."

# 2. Migrationen ausfuehren (einmal, sequentiell, vor Gunicorn)
echo "Fuehre Migrationen aus..."
if ! flask db upgrade; then
    echo "WARNUNG: Migration fehlgeschlagen (evtl. bereits aktuell)"
    echo "Versuche trotzdem fortzufahren..."
fi

# 3. Admin-Benutzer erstellen falls noetig
echo "Pruefe Admin-Benutzer..."
python -c "
from app import create_app, db
from app.models.user import User
import os
app = create_app(os.getenv('FLASK_ENV', 'production'))
with app.app_context():
    if User.query.count() == 0:
        admin = User(username='admin', email='admin@agro.de', vorname='Administrator', nachname='System', rolle='betriebsadmin', aktiv=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print('Admin-Benutzer erstellt (admin / admin123)')
    else:
        print(f'{User.query.count()} Benutzer vorhanden, ueberspringe')
"

echo "=== Starte Gunicorn ==="
exec gunicorn \
    --bind 0.0.0.0:5000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    wsgi:app
