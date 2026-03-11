from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.maschine import Maschine, Einsatz
from app.models.user import User
from datetime import datetime

maschinen_bp = Blueprint('maschinen', __name__, url_prefix='/maschinen')


@maschinen_bp.route('/')
@login_required
def index():
    """Maschinenliste."""
    maschinen = Maschine.query.filter_by(aktiv=True).order_by(Maschine.name).all()
    return render_template('maschinen/index.html', maschinen=maschinen)


@maschinen_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    """Neue Maschine."""
    if request.method == 'POST':
        maschine = Maschine(
            name=request.form.get('name', '').strip(),
            beschreibung=request.form.get('beschreibung', '').strip() or None,
            kennzeichen=request.form.get('kennzeichen', '').strip() or None,
            baujahr=request.form.get('baujahr', type=int) or None,
            buchungsmodus=request.form.get('buchungsmodus', 'direkt'),
            zaehler_format=request.form.get('zaehler_format', 'dezimal'),
            einheit=request.form.get('einheit', 'h'),
            kosten_pro_einheit=request.form.get('kosten_pro_einheit', type=float) or None,
            anschaffungswert=request.form.get('anschaffungswert', type=float) or None,
        )
        db.session.add(maschine)
        db.session.commit()
        flash(f'Maschine "{maschine.name}" erstellt.', 'success')
        return redirect(url_for('maschinen.index'))
    
    return render_template('maschinen/form.html', maschine=None)


@maschinen_bp.route('/<int:id>')
@login_required
def detail(id):
    """Maschinen-Detail + Einsatzprotokoll."""
    maschine = Maschine.query.get_or_404(id)
    einsaetze = maschine.einsaetze.order_by(Einsatz.datum.desc()).all()
    return render_template('maschinen/detail.html', maschine=maschine, einsaetze=einsaetze)


@maschinen_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Maschine bearbeiten."""
    maschine = Maschine.query.get_or_404(id)
    
    if request.method == 'POST':
        maschine.name = request.form.get('name', '').strip()
        maschine.beschreibung = request.form.get('beschreibung', '').strip() or None
        maschine.kennzeichen = request.form.get('kennzeichen', '').strip() or None
        maschine.baujahr = request.form.get('baujahr', type=int) or None
        maschine.buchungsmodus = request.form.get('buchungsmodus', 'direkt')
        maschine.zaehler_format = request.form.get('zaehler_format', 'dezimal')
        maschine.einheit = request.form.get('einheit', 'h')
        maschine.kosten_pro_einheit = request.form.get('kosten_pro_einheit', type=float) or None
        maschine.anschaffungswert = request.form.get('anschaffungswert', type=float) or None
        db.session.commit()
        flash(f'Maschine "{maschine.name}" gespeichert.', 'success')
        return redirect(url_for('maschinen.detail', id=maschine.id))
    
    return render_template('maschinen/form.html', maschine=maschine)


@maschinen_bp.route('/<int:id>/einsatz', methods=['POST'])
@login_required
def add_einsatz(id):
    """Einsatz hinzufügen."""
    maschine = Maschine.query.get_or_404(id)
    
    einsatz = Einsatz(
        maschine_id=id,
        erstellt_von_id=current_user.id,
        datum=datetime.strptime(request.form.get('datum', ''), '%Y-%m-%d').date(),
        von=datetime.strptime(request.form.get('von', ''), '%H:%M').time() if request.form.get('von') else None,
        bis=datetime.strptime(request.form.get('bis', ''), '%H:%M').time() if request.form.get('bis') else None,
        menge=float(request.form.get('menge', 0)),
        zaehlerstand_start=request.form.get('zaehlerstand_start', '').strip() or None,
        zaehlerstand_ende=request.form.get('zaehlerstand_ende', '').strip() or None,
        notiz=request.form.get('notiz', '').strip() or None,
        kostenart=request.form.get('kostenart', '').strip() or None,
        kosten=request.form.get('kosten', type=float) or None,
    )
    db.session.add(einsatz)
    db.session.commit()
    flash('Einsatz erfasst.', 'success')
    return redirect(url_for('maschinen.detail', id=id))
