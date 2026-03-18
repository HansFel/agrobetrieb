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


def _lade_tierarzt_stats():
    """Statistiken für Tierarzt-Dashboard."""
    stats = {}
    heute = date.today()
    try:
        from app.models.legehennen import Herde, TierarztBesuch, MedikamentBehandlung
        stats['herden_aktiv'] = Herde.query.filter_by(ist_aktiv=True).count()
        stats['tierarzt_besuche_30d'] = TierarztBesuch.query.filter(
            TierarztBesuch.datum >= heute.replace(day=1)
        ).count()
        stats['wartezeiten_aktiv'] = MedikamentBehandlung.query.filter(
            MedikamentBehandlung.wartezeit_ende >= heute
        ).count()
        # Offene Signaturen Legehennen
        offene_lh = TierarztBesuch.query.filter(
            TierarztBesuch.signatur_data == None
        ).count()
    except Exception:
        db.session.rollback()
        offene_lh = 0
    try:
        from app.models.milchvieh import Rind, RindArzneimittelAnwendung
        stats['rinder_aktiv'] = Rind.query.filter_by(status='aktiv').count()
        # Offene Signaturen TAMG Milchvieh
        offene_mv = RindArzneimittelAnwendung.query.filter(
            RindArzneimittelAnwendung.signatur_data == None
        ).count()
        # Aktive Wartezeiten Milchvieh
        wz_mv = RindArzneimittelAnwendung.query.filter(
            (RindArzneimittelAnwendung.wartezeit_milch_ende >= heute) |
            (RindArzneimittelAnwendung.wartezeit_fleisch_ende >= heute)
        ).count()
        stats['wartezeiten_aktiv'] = stats.get('wartezeiten_aktiv', 0) + wz_mv
    except Exception:
        db.session.rollback()
        offene_mv = 0
    stats['offene_signaturen'] = offene_lh + offene_mv
    return stats


@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard-Startseite – Inhalt je nach Rolle."""
    betrieb = Betrieb.query.first()
    rolle = current_user.rolle
    stats = _lade_statistiken(rolle)

    # Tierarzt/Amtstierarzt → eigenes Dashboard
    if rolle in ('tierarzt', 'amtstierarzt'):
        herden_aktiv = []
        try:
            from app.models.legehennen import Herde
            herden_aktiv = Herde.query.filter_by(ist_aktiv=True).order_by(Herde.name).all()
        except Exception:
            db.session.rollback()
        tamg_eintraege = []
        try:
            from app.models.milchvieh import RindArzneimittelAnwendung, Rind
            tamg_eintraege = (RindArzneimittelAnwendung.query
                              .join(Rind)
                              .filter(Rind.status == 'aktiv')
                              .order_by(RindArzneimittelAnwendung.beginn.desc())
                              .limit(20).all())
        except Exception:
            db.session.rollback()
        return render_template('dashboard/tierarzt.html',
                               betrieb=betrieb, rolle=rolle,
                               stats=_lade_tierarzt_stats(),
                               herden_aktiv=herden_aktiv,
                               tamg_eintraege=tamg_eintraege)

    # Externe Apps für diesen Betrieb laden
    externe_apps = []
    try:
        from app.models.externe_app import ExterneApp, BetriebExterneApp
        if betrieb:
            verknuepfungen = BetriebExterneApp.query.filter_by(betrieb_id=betrieb.id).all()
            app_ids = [v.app_id for v in verknuepfungen]
            if app_ids:
                externe_apps = ExterneApp.query.filter(
                    ExterneApp.id.in_(app_ids), ExterneApp.aktiv == True
                ).order_by(ExterneApp.reihenfolge).all()
    except Exception:
        db.session.rollback()

    context = {
        'betrieb': betrieb,
        'rolle': rolle,
        'stats': stats,
        'externe_apps': externe_apps,
    }
    return render_template('dashboard/index.html', **context)
