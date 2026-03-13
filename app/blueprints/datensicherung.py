"""
Datensicherung-Blueprint: Backup erstellen, wiederherstellen, herunterladen, löschen, hochladen.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, request
from flask_login import login_required, current_user
from app.auth_decorators import requires_admin
from app.services.backup_service import (
    backup_erstellen, backup_wiederherstellen, backup_loeschen, backup_liste,
    backup_upload, backup_statistik, aufbewahrung_aufraeumen
)

datensicherung_bp = Blueprint('datensicherung', __name__, url_prefix='/datensicherung')


@datensicherung_bp.route('/')
@login_required
@requires_admin()
def index():
    """Übersicht aller Backups mit Strategie-Info."""
    backups = backup_liste()
    statistik = backup_statistik()
    return render_template('datensicherung/index.html', backups=backups, statistik=statistik)


@datensicherung_bp.route('/erstellen', methods=['POST'])
@login_required
@requires_admin()
def erstellen():
    """Neues Backup erstellen."""
    try:
        backup = backup_erstellen(user_id=current_user.id, typ='manuell')
        flash(f'Backup erfolgreich erstellt: {backup.dateiname} ({backup.groesse_formatiert})', 'success')
    except Exception as e:
        flash(f'Backup fehlgeschlagen: {e}', 'danger')
    return redirect(url_for('datensicherung.index'))


@datensicherung_bp.route('/wiederherstellen/<int:backup_id>', methods=['POST'])
@login_required
@requires_admin()
def wiederherstellen(backup_id):
    """Backup wiederherstellen."""
    try:
        backup_wiederherstellen(backup_id)
        flash('Backup wurde erfolgreich wiederhergestellt. Bitte App neu starten.', 'success')
    except Exception as e:
        flash(f'Wiederherstellung fehlgeschlagen: {e}', 'danger')
    return redirect(url_for('datensicherung.index'))


@datensicherung_bp.route('/herunterladen/<int:backup_id>')
@login_required
@requires_admin()
def herunterladen(backup_id):
    """Backup-Datei herunterladen."""
    from app.models.backup import Backup
    import os
    backup = Backup.query.get_or_404(backup_id)
    if not os.path.exists(backup.dateipfad):
        flash('Backup-Datei nicht gefunden', 'danger')
        return redirect(url_for('datensicherung.index'))
    return send_file(backup.dateipfad, as_attachment=True, download_name=backup.dateiname)


@datensicherung_bp.route('/loeschen/<int:backup_id>', methods=['POST'])
@login_required
@requires_admin()
def loeschen(backup_id):
    """Backup löschen."""
    try:
        backup_loeschen(backup_id)
        flash('Backup gelöscht', 'success')
    except Exception as e:
        flash(f'Löschen fehlgeschlagen: {e}', 'danger')
    return redirect(url_for('datensicherung.index'))


@datensicherung_bp.route('/hochladen', methods=['POST'])
@login_required
@requires_admin()
def hochladen():
    """Externes Backup hochladen."""
    if 'backup_datei' not in request.files:
        flash('Keine Datei ausgewählt', 'warning')
        return redirect(url_for('datensicherung.index'))

    datei = request.files['backup_datei']
    try:
        backup = backup_upload(datei, user_id=current_user.id)
        flash(f'Backup hochgeladen: {backup.dateiname} ({backup.groesse_formatiert})', 'success')
    except ValueError as e:
        flash(str(e), 'warning')
    except Exception as e:
        flash(f'Upload fehlgeschlagen: {e}', 'danger')
    return redirect(url_for('datensicherung.index'))


@datensicherung_bp.route('/aufraeumen', methods=['POST'])
@login_required
@requires_admin()
def aufraeumen():
    """Aufbewahrungsrichtlinie manuell anwenden."""
    try:
        geloescht = aufbewahrung_aufraeumen()
        if geloescht > 0:
            flash(f'{geloescht} alte Backup(s) aufgeräumt', 'info')
        else:
            flash('Keine Backups zum Aufräumen gefunden', 'info')
    except Exception as e:
        flash(f'Aufräumen fehlgeschlagen: {e}', 'danger')
    return redirect(url_for('datensicherung.index'))
