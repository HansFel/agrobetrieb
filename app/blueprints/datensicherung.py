"""
Datensicherung-Blueprint: Backup erstellen, wiederherstellen, herunterladen, löschen.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, send_file, request
from flask_login import login_required, current_user
from app.auth_decorators import requires_admin
from app.services.backup_service import (
    backup_erstellen, backup_wiederherstellen, backup_loeschen, backup_liste
)

datensicherung_bp = Blueprint('datensicherung', __name__, url_prefix='/datensicherung')


@datensicherung_bp.route('/')
@login_required
@requires_admin()
def index():
    """Übersicht aller Backups."""
    backups = backup_liste()
    return render_template('datensicherung/index.html', backups=backups)


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
