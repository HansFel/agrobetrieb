from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.extensions import db
from app.models.buchhaltung import Konto, Kategorie, Buchung
from datetime import datetime

buchhaltung_bp = Blueprint('buchhaltung', __name__, url_prefix='/buchhaltung')


@buchhaltung_bp.route('/')
@login_required
def index():
    """Buchhaltungs-Übersicht."""
    buchungen = Buchung.query.order_by(Buchung.datum.desc()).limit(20).all()
    gesamt_ausgaben = db.session.query(db.func.sum(Buchung.betrag)).filter(Buchung.haben_konto_id.isnot(None)).scalar() or 0
    gesamt_einnahmen = db.session.query(db.func.sum(Buchung.betrag)).filter(Buchung.soll_konto_id.isnot(None)).scalar() or 0
    
    return render_template('buchhaltung/index.html', 
                         buchungen=buchungen,
                         gesamt_ausgaben=gesamt_ausgaben,
                         gesamt_einnahmen=gesamt_einnahmen)


@buchhaltung_bp.route('/buchung/new', methods=['GET', 'POST'])
@login_required
def create_buchung():
    """Neue Buchung."""
    konten = Konto.query.order_by(Konto.nummer).all()
    kategorien = Kategorie.query.order_by(Kategorie.name).all()
    
    if request.method == 'POST':
        try:
            mwst_satz = float(request.form.get('mwst_satz', 0)) or 0
            mwst_betrag = float(request.form.get('mwst_betrag', 0)) or 0
            
            buchung = Buchung(
                datum=datetime.strptime(request.form.get('datum', ''), '%Y-%m-%d').date(),
                valuta=datetime.strptime(request.form.get('valuta', request.form.get('datum')), '%Y-%m-%d').date() if request.form.get('valuta') else None,
                beschreibung=request.form.get('beschreibung', '').strip() or None,
                betrag=float(request.form.get('betrag', 0)),
                haben_konto_id=request.form.get('haben_konto_id', type=int) or None,
                soll_konto_id=request.form.get('soll_konto_id', type=int) or None,
                kategorie_id=request.form.get('kategorie_id', type=int) or None,
                beleg_nummer=request.form.get('beleg_nummer', '').strip() or None,
                mwst_satz=mwst_satz,
                mwst_betrag=mwst_betrag,
                bezahlt=request.form.get('bezahlt') == 'on',
                erstellt_von_id=1,  # TODO: current_user.id
            )
            db.session.add(buchung)
            db.session.commit()
            flash('Buchung erstellt.', 'success')
            return redirect(url_for('buchhaltung.index'))
        except (ValueError, KeyError) as e:
            flash('Fehler beim Erstellen der Buchung.', 'danger')
    
    return render_template('buchhaltung/buchung_form.html', konten=konten, kategorien=kategorien)


@buchhaltung_bp.route('/kategorie')
@login_required
def kategorien():
    """Kategorienliste."""
    kategorien = Kategorie.query.all()
    return render_template('buchhaltung/kategorien.html', kategorien=kategorien)


@buchhaltung_bp.route('/konto')
@login_required
def konten():
    """Kontenliste."""
    konten = Konto.query.all()
    return render_template('buchhaltung/konten.html', konten=konten)
