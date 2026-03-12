"""
Blueprint: Benutzerverwaltung (Admin)
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.user import User
from app.auth_decorators import requires_admin
from app.models.rollen import ROLLEN

benutzer_bp = Blueprint('benutzer', __name__, url_prefix='/benutzer')


@benutzer_bp.route('/')
@login_required
@requires_admin()
def liste():
    """Alle Benutzer auflisten."""
    benutzer = User.query.order_by(User.erstellt_am.desc()).all()
    rollen = ROLLEN
    return render_template('benutzer/liste.html', benutzer=benutzer, rollen=rollen)


@benutzer_bp.route('/neu', methods=['GET', 'POST'])
@login_required
@requires_admin()
def neu():
    """Neuen Benutzer anlegen."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        vorname = request.form.get('vorname', '').strip()
        nachname = request.form.get('nachname', '').strip()
        rolle = request.form.get('rolle', 'praktikand')
        passwort = request.form.get('passwort', '').strip()
        
        # Validierung
        if not username or not email or not passwort:
            flash('Username, Email und Passwort sind erforderlich', 'danger')
            return redirect(url_for('benutzer.neu'))
        
        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" existiert bereits', 'danger')
            return redirect(url_for('benutzer.neu'))
        
        if User.query.filter_by(email=email).first():
            flash(f'Email "{email}" existiert bereits', 'danger')
            return redirect(url_for('benutzer.neu'))
        
        # Benutzer anlegen
        benutzer = User(
            username=username,
            email=email,
            vorname=vorname,
            nachname=nachname,
            rolle=rolle,
            aktiv=True
        )
        benutzer.set_password(passwort)
        
        db.session.add(benutzer)
        db.session.commit()
        
        flash(f'Benutzer "{username}" wurde angelegt', 'success')
        return redirect(url_for('benutzer.liste'))
    
    rollen = ROLLEN
    return render_template('benutzer/form.html', benutzer=None, rollen=rollen)


@benutzer_bp.route('/<int:benutzer_id>/bearbeiten', methods=['GET', 'POST'])
@login_required
@requires_admin()
def bearbeiten(benutzer_id):
    """Benutzer bearbeiten."""
    benutzer = User.query.get_or_404(benutzer_id)
    
    if request.method == 'POST':
        benutzer.vorname = request.form.get('vorname', '').strip()
        benutzer.nachname = request.form.get('nachname', '').strip()
        benutzer.email = request.form.get('email', '').strip()
        benutzer.rolle = request.form.get('rolle', benutzer.rolle)
        benutzer.aktiv = request.form.get('aktiv') == 'on'
        
        new_passwort = request.form.get('passwort', '').strip()
        if new_passwort:
            benutzer.set_password(new_passwort)
        
        db.session.commit()
        flash(f'Benutzer "{benutzer.username}" wurde aktualisiert', 'success')
        return redirect(url_for('benutzer.liste'))
    
    rollen = ROLLEN
    return render_template('benutzer/form.html', benutzer=benutzer, rollen=rollen)


@benutzer_bp.route('/<int:benutzer_id>/loeschen', methods=['POST'])
@login_required
@requires_admin()
def loeschen(benutzer_id):
    """Benutzer löschen."""
    benutzer = User.query.get_or_404(benutzer_id)
    
    # Sich selbst nicht löschen
    if benutzer.id == current_user.id:
        flash('Du kannst deinen eigenen Account nicht löschen', 'danger')
        return redirect(url_for('benutzer.liste'))
    
    username = benutzer.username
    db.session.delete(benutzer)
    db.session.commit()
    
    flash(f'Benutzer "{username}" wurde gelöscht', 'success')
    return redirect(url_for('benutzer.liste'))
