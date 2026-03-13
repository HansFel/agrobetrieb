#!/bin/bash
set -e

echo "=== AgroBetrieb Startup ==="

# 1. Warte auf Datenbank
echo "Warte auf Datenbank..."
until pg_isready -h agrobetrieb-db -p 5432 -U agr_user -q; do
    echo "  DB noch nicht bereit, warte 2s..."
    sleep 2
done
echo "DB bereit."

# 2. Migrationen ausfuehren (einmal, sequentiell, vor Gunicorn)
echo "Fuehre Migrationen aus..."
flask db upgrade || echo "WARNUNG: Migration fehlgeschlagen (evtl. bereits aktuell)"

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
