from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login-Seite."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        login_input = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Unterstütze sowohl username als auch email als Login
        user = User.query.filter(
            (User.username == login_input) | (User.email == login_input)
        ).first()
        
        if user and user.check_password(password) and user.aktiv:
            login_user(user)
            if user.muss_passwort_aendern:
                flash('Bitte ändern Sie Ihr Passwort bevor Sie fortfahren.', 'warning')
                return redirect(url_for('auth.passwort_aendern'))
            flash(f'Willkommen, {user.vorname or user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Ungültiger Benutzername/Email oder Passwort.', 'danger')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Logout."""
    logout_user()
    flash('Sie wurden abgemeldet.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/passwort-aendern', methods=['GET', 'POST'])
@login_required
def passwort_aendern():
    """Passwort ändern."""
    if request.method == 'POST':
        altes_pw = request.form.get('altes_passwort', '')
        neues_pw = request.form.get('neues_passwort', '')
        neues_pw2 = request.form.get('neues_passwort2', '')
        
        if not current_user.check_password(altes_pw):
            flash('Das alte Passwort ist falsch.', 'danger')
        elif neues_pw != neues_pw2:
            flash('Die neuen Passwörter stimmen nicht überein.', 'danger')
        elif len(neues_pw) < 6:
            flash('Das neue Passwort muss mindestens 6 Zeichen lang sein.', 'danger')
        else:
            current_user.set_password(neues_pw)
            current_user.muss_passwort_aendern = False
            db.session.commit()
            flash('Passwort wurde erfolgreich geändert.', 'success')
            return redirect(url_for('dashboard.index'))
    
    return render_template('auth/passwort_aendern.html')


@auth_bp.route('/profil', methods=['GET', 'POST'])
@login_required
def profil():
    """Benutzerprofil."""
    if request.method == 'POST':
        current_user.vorname = request.form.get('vorname', '').strip() or None
        current_user.nachname = request.form.get('nachname', '').strip() or current_user.nachname
        current_user.telefon = request.form.get('telefon', '').strip() or None
        current_user.email = request.form.get('email', '').strip() or current_user.email
        db.session.commit()
        flash('Profil gespeichert.', 'success')
        return redirect(url_for('auth.profil'))
    
    return render_template('auth/profil.html')
