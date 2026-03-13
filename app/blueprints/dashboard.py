from datetime import datetime, date
from flask import Blueprint, render_template
from flask_login import login_required, current_user
from sqlalchemy import func
from app.extensions import db
from app.models.betrieb import Betrieb
from app.models.user import User
from app.models.rollen import hat_berechtigung

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')


def _lade_statistiken(rolle):
    """Lädt rollenspezifische Statistiken."""
    stats = {}
    heute = date.today()
    monat_start = heute.replace(day=1)

    # Einsätze diesen Monat (wenn Rolle Zugriff hat)
    if hat_berechtigung(current_user, 'einsaetze', 'view'):
        try:
            from app.models.maschine import Einsatz
            stats['einsaetze_monat'] = Einsatz.query.filter(
                Einsatz.datum >= monat_start
            ).count()
        except Exception:
            db.session.rollback()
            stats['einsaetze_monat'] = 0
    
    # Offene Rechnungen (wenn Rolle Zugriff hat)
    if hat_berechtigung(current_user, 'fakturierung', 'view'):
        try:
            from app.models.fakturierung import Faktura
            stats['rechnungen_offen'] = Faktura.query.filter(
                Faktura.status == 'offen'
            ).count()
        except Exception:
            db.session.rollback()
            stats['rechnungen_offen'] = 0

    # Maschinen-Anzahl
    if hat_berechtigung(current_user, 'maschinen', 'view'):
        try:
            from app.models.maschine import Maschine
            stats['maschinen_gesamt'] = Maschine.query.count()
        except Exception:
            db.session.rollback()
            stats['maschinen_gesamt'] = 0

    # Admin-spezifisch: Benutzeranzahl
    if rolle == 'betriebsadmin':
        stats['benutzer_gesamt'] = User.query.filter_by(aktiv=True).count()

    # Buchhaltung: Letzter Kontostand
    if hat_berechtigung(current_user, 'buchhaltung', 'view'):
        try:
            from app.models.buchhaltung import Buchung
            stats['buchungen_monat'] = Buchung.query.filter(
                Buchung.datum >= monat_start
            ).count()
        except Exception:
            db.session.rollback()
            stats['buchungen_monat'] = 0

    return stats


@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard-Startseite – Inhalt je nach Rolle."""
    betrieb = Betrieb.query.first()
    rolle = current_user.rolle
    stats = _lade_statistiken(rolle)

    context = {
        'betrieb': betrieb,
        'rolle': rolle,
        'stats': stats,
    }
    return render_template('dashboard/index.html', **context)
