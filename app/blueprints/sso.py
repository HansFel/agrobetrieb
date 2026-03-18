"""
SSO-Blueprint für AgroBetrieb.

Routen:
  GET  /sso/zu/<kuerzel>      – Token ausstellen + Redirect zu externer App
  GET  /sso/eingang           – Token empfangen (Reserveroute)
  GET  /sso/apps              – Admin: Alle externen Apps verwalten
  POST /sso/apps/neu          – Admin: Neue App anlegen
  POST /sso/apps/<id>/edit    – Admin: App bearbeiten (nur eigene)
  POST /sso/apps/<id>/delete  – Admin: App löschen (nur eigene)
"""
import os
from flask import Blueprint, redirect, url_for, abort, request, flash, render_template
from flask_login import login_required, current_user
from app.models.sso_token import SsoToken
from app.models.externe_app import ExterneApp, BetriebExterneApp
from app.extensions import db

sso_bp = Blueprint('sso', __name__, url_prefix='/sso')


def _ist_admin():
    """Betriebsadmin oder Superadmin."""
    return getattr(current_user, 'ist_superadmin', False) or current_user.rolle == 'betriebsadmin'


@sso_bp.route('/zu/<kuerzel>')
@login_required
def zu_externer_app(kuerzel: str):
    """SSO-Token ausstellen und zu externer App weiterleiten."""
    from app.models.betrieb import Betrieb
    betrieb = Betrieb.query.first()

    app_obj = ExterneApp.query.filter_by(kuerzel=kuerzel, aktiv=True).first()
    if not app_obj:
        abort(404)

    # Superadmin darf immer, andere nur wenn App für Betrieb freigeschaltet
    if not getattr(current_user, 'ist_superadmin', False):
        if betrieb:
            verknuepft = BetriebExterneApp.query.filter_by(
                betrieb_id=betrieb.id, app_id=app_obj.id
            ).first()
            if not verknuepft:
                flash('Diese App ist für Ihren Betrieb nicht freigeschaltet.', 'warning')
                return redirect(url_for('dashboard.index'))

    token = SsoToken.ausstellen(
        username=current_user.username,
        ziel_instanz=kuerzel,
    )

    basis = app_obj.basis_url.rstrip('/')
    ziel_url = f'{basis}/auth/sso-eingang?token={token.token}'
    return redirect(ziel_url)


@sso_bp.route('/eingang')
@login_required
def eingang():
    """Reserveroute falls AgroBetrieb selbst SSO-Ziel ist."""
    return redirect(url_for('dashboard.index'))


# ── App-Verwaltung (Betriebsadmin + Superadmin) ───────────────────────────────

@sso_bp.route('/apps')
@login_required
def apps_liste():
    if not _ist_admin():
        abort(403)
    apps = ExterneApp.query.order_by(ExterneApp.reihenfolge, ExterneApp.name).all()
    return render_template('sso/apps_liste.html', apps=apps)


@sso_bp.route('/apps/neu', methods=['GET', 'POST'])
@login_required
def app_neu():
    if not _ist_admin():
        abort(403)
    if request.method == 'POST':
        kuerzel = request.form.get('kuerzel', '').strip()
        # Kürzel muss eindeutig sein
        if ExterneApp.query.filter_by(kuerzel=kuerzel).first():
            flash(f'Kürzel „{kuerzel}" ist bereits vergeben.', 'danger')
            return render_template('sso/app_form.html', app=None)
        app_obj = ExterneApp(
            name=request.form.get('name', '').strip(),
            kuerzel=kuerzel,
            basis_url=request.form.get('basis_url', '').strip().rstrip('/'),
            icon=request.form.get('icon', 'bi-box-arrow-up-right').strip(),
            beschreibung=request.form.get('beschreibung', '').strip() or None,
            aktiv=request.form.get('aktiv') == '1',
            reihenfolge=int(request.form.get('reihenfolge', 0) or 0),
        )
        db.session.add(app_obj)
        db.session.commit()
        flash(f'App „{app_obj.name}" angelegt.', 'success')
        return redirect(url_for('sso.apps_liste'))
    return render_template('sso/app_form.html', app=None)


@sso_bp.route('/apps/<int:app_id>/edit', methods=['GET', 'POST'])
@login_required
def app_edit(app_id: int):
    if not _ist_admin():
        abort(403)
    app_obj = ExterneApp.query.get_or_404(app_id)
    if request.method == 'POST':
        app_obj.name = request.form.get('name', '').strip()
        app_obj.kuerzel = request.form.get('kuerzel', '').strip()
        app_obj.basis_url = request.form.get('basis_url', '').strip().rstrip('/')
        app_obj.icon = request.form.get('icon', 'bi-box-arrow-up-right').strip()
        app_obj.beschreibung = request.form.get('beschreibung', '').strip() or None
        app_obj.aktiv = request.form.get('aktiv') == '1'
        app_obj.reihenfolge = int(request.form.get('reihenfolge', 0) or 0)
        db.session.commit()
        flash(f'App „{app_obj.name}" gespeichert.', 'success')
        return redirect(url_for('sso.apps_liste'))
    return render_template('sso/app_form.html', app=app_obj)


@sso_bp.route('/apps/<int:app_id>/delete', methods=['POST'])
@login_required
def app_delete(app_id: int):
    if not _ist_admin():
        abort(403)
    app_obj = ExterneApp.query.get_or_404(app_id)
    db.session.delete(app_obj)
    db.session.commit()
    flash(f'App „{app_obj.name}" gelöscht.', 'success')
    return redirect(url_for('sso.apps_liste'))
