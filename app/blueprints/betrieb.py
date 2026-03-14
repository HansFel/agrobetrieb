from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.betrieb import Betrieb

betrieb_bp = Blueprint('betrieb', __name__, url_prefix='/betrieb')


def check_admin():
    """Nur Admin darf Betrieb bearbeiten."""
    if not current_user.is_admin():
        flash('Zugriff verweigert.', 'danger')
        return False
    return True


@betrieb_bp.route('/')
@login_required
def index():
    """Betrieb-Übersicht."""
    betrieb = Betrieb.query.first()
    if not betrieb:
        return redirect(url_for('betrieb.create'))
    return render_template('betrieb/index.html', betrieb=betrieb)


@betrieb_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    """Betrieb erstellen."""
    if not check_admin():
        return redirect(url_for('dashboard.index'))
    
    if Betrieb.query.first():
        flash('Es existiert bereits ein Betrieb.', 'warning')
        return redirect(url_for('betrieb.index'))
    
    if request.method == 'POST':
        betrieb = Betrieb(
            name=request.form.get('name', '').strip(),
            strasse=request.form.get('strasse', '').strip() or None,
            plz=request.form.get('plz', '').strip() or None,
            ort=request.form.get('ort', '').strip() or None,
            land=request.form.get('land', 'AT'),
            waehrung=request.form.get('waehrung', '€'),
            mwst_satz_standard=request.form.get('mwst_satz_standard', 20),
            uid_nummer=request.form.get('uid_nummer', '').strip() or None,
            steuernummer=request.form.get('steuernummer', '').strip() or None,
            iban=request.form.get('iban', '').strip() or None,
            bic=request.form.get('bic', '').strip() or None,
            bank_name=request.form.get('bank_name', '').strip() or None,
            telefon=request.form.get('telefon', '').strip() or None,
            email=request.form.get('email', '').strip() or None,
            website=request.form.get('website', '').strip() or None,
            ist_testbetrieb=current_user.ist_superadmin and request.form.get('ist_testbetrieb') == '1',
            modul_legehennen=current_user.ist_superadmin and request.form.get('modul_legehennen') == '1',
        )
        db.session.add(betrieb)
        db.session.commit()
        flash('Betrieb erstellt.', 'success')
        return redirect(url_for('betrieb.index'))
    
    return render_template('betrieb/form.html', betrieb=None)


@betrieb_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    """Betrieb bearbeiten."""
    if not check_admin():
        return redirect(url_for('dashboard.index'))
    
    betrieb = Betrieb.query.first_or_404()
    
    if request.method == 'POST':
        betrieb.name = request.form.get('name', '').strip()
        betrieb.strasse = request.form.get('strasse', '').strip() or None
        betrieb.plz = request.form.get('plz', '').strip() or None
        betrieb.ort = request.form.get('ort', '').strip() or None
        betrieb.land = request.form.get('land', 'AT')
        betrieb.waehrung = request.form.get('waehrung', '€')
        betrieb.mwst_satz_standard = request.form.get('mwst_satz_standard', 20)
        betrieb.uid_nummer = request.form.get('uid_nummer', '').strip() or None
        betrieb.steuernummer = request.form.get('steuernummer', '').strip() or None
        betrieb.iban = request.form.get('iban', '').strip() or None
        betrieb.bic = request.form.get('bic', '').strip() or None
        betrieb.bank_name = request.form.get('bank_name', '').strip() or None
        betrieb.telefon = request.form.get('telefon', '').strip() or None
        betrieb.email = request.form.get('email', '').strip() or None
        betrieb.website = request.form.get('website', '').strip() or None
        if current_user.ist_superadmin:
            betrieb.ist_testbetrieb = request.form.get('ist_testbetrieb') == '1'
            betrieb.modul_legehennen = request.form.get('modul_legehennen') == '1'
        db.session.commit()
        flash('Betrieb gespeichert.', 'success')
        return redirect(url_for('betrieb.index'))
    
    return render_template('betrieb/form.html', betrieb=betrieb)
