from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required
from app.extensions import db
from app.models.fakturierung import Kunde, Rechnung, RechnungsPosition
from datetime import datetime, timedelta
from sqlalchemy import func

fakturierung_bp = Blueprint('fakturierung', __name__, url_prefix='/fakturierung')


@fakturierung_bp.route('/')
@login_required
def index():
    """Rechnungsübersicht."""
    rechnungen = Rechnung.query.order_by(Rechnung.datum.desc()).all()
    status_counts = {
        'offen': len([r for r in rechnungen if r.status == 'offen']),
        'bezahlt': len([r for r in rechnungen if r.status == 'bezahlt']),
        'storno': len([r for r in rechnungen if r.status == 'storno'])
    }
    return render_template('fakturierung/index.html', rechnungen=rechnungen, status_counts=status_counts, now=datetime.now())


@fakturierung_bp.route('/rechnung/new', methods=['GET', 'POST'])
@login_required
def create_rechnung():
    """Neue Rechnung."""
    kunden = Kunde.query.all()
    
    if request.method == 'POST':
        # Nummern-Generator (vereinfacht)
        last = Rechnung.query.order_by(Rechnung.id.desc()).first()
        rechnung_nr = f"RG-{datetime.now().year}-{(last.id if last else 0) + 1:04d}"
        
        rechnung = Rechnung(
            nummer=rechnung_nr,
            kunde_id=request.form.get('kunde_id', type=int),
            datum=datetime.strptime(request.form.get('datum', ''), '%Y-%m-%d').date(),
            faellig_am=datetime.strptime(request.form.get('datum', ''), '%Y-%m-%d').date() + timedelta(days=14),
            notiz=request.form.get('notiz', '').strip() or None,
            status='offen',
        )
        db.session.add(rechnung)
        db.session.commit()
        flash(f'Rechnung {rechnung_nr} erstellt.', 'success')
        return redirect(url_for('fakturierung.detail', id=rechnung.id))
    
    return render_template('fakturierung/rechnung_form.html', kunden=kunden, rechnung=None)


@fakturierung_bp.route('/rechnung/<int:id>')
@login_required
def detail(id):
    """Rechnungs-Detail."""
    rechnung = Rechnung.query.get_or_404(id)
    return render_template('fakturierung/rechnung_detail.html', rechnung=rechnung)


@fakturierung_bp.route('/kunden')
@login_required
def kunden():
    """Kundenliste."""
    kunden = Kunde.query.all()
    return render_template('fakturierung/kunden.html', kunden=kunden)


@fakturierung_bp.route('/kunde/new', methods=['GET', 'POST'])
@login_required
def create_kunde():
    """Neuer Kunde."""
    if request.method == 'POST':
        try:
            kunde = Kunde(
                name=request.form.get('name', '').strip(),
                beschreibung=request.form.get('beschreibung', '').strip() or None,
                strasse=request.form.get('strasse', '').strip() or None,
                plz=request.form.get('plz', '').strip() or None,
                ort=request.form.get('ort', '').strip() or None,
                land=request.form.get('land', 'Schweiz'),
                uid_nummer=request.form.get('uid_nummer', '').strip() or None,
                email=request.form.get('email', '').strip() or None,
                telefon=request.form.get('telefon', '').strip() or None,
                kontakt=request.form.get('kontakt', '').strip() or None,
            )
            db.session.add(kunde)
            db.session.commit()
            
            # AJAX/Modal response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': f'Kunde "{kunde.name}" erstellt.'})
            
            flash(f'Kunde "{kunde.name}" erstellt.', 'success')
            return redirect(url_for('fakturierung.kunden'))
        except Exception as e:
            db.session.rollback()
            flash('Fehler beim Erstellen des Kunden.', 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': str(e)}), 400
    
    return render_template('fakturierung/kunde_form.html', kunde=None)
