from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app.extensions import db
from app.models.lager import LagerArtikel, LagerBewegung
from datetime import datetime

lager_bp = Blueprint('lager', __name__, url_prefix='/lager')

# Context processor for template
@lager_bp.context_processor
def lager_context():
    """Lager context for templates."""
    return {
        'now': datetime.now()
    }


@lager_bp.route('/')
@login_required
def index():
    """Lagerübersicht."""
    artikel = LagerArtikel.query.filter_by(aktiv=True).all()
    artikel_unter_mindest = [a for a in artikel if a.unter_mindestbestand]
    artikel_aktiv = [a for a in artikel if a.aktiv]
    gesamtwert = sum(a.aktueller_bestand * (a.letzter_einkaufspreis or 0) for a in artikel)
    
    return render_template('lager/index.html', 
                         artikel=artikel, 
                         artikel_unter_mindest=artikel_unter_mindest,
                         artikel_aktiv=artikel_aktiv,
                         gesamtwert=gesamtwert)


@lager_bp.route('/artikel/new', methods=['GET', 'POST'])
@login_required
def create_artikel():
    """Neuer Lagerartikel."""
    if request.method == 'POST':
        try:
            artikel = LagerArtikel(
                bezeichnung=request.form.get('bezeichnung', '').strip(),
                beschreibung=request.form.get('beschreibung', '').strip() or None,
                artikelnummer=request.form.get('artikelnummer', '').strip() or None,
                einheit=request.form.get('einheit', 'Stk'),
                aktueller_bestand=float(request.form.get('aktueller_bestand', 0)) or 0,
                mindestbestand=float(request.form.get('mindestbestand', 0)) or 0,
                letzter_einkaufspreis=float(request.form.get('letzter_einkaufspreis', 0)) or None,
                aktiv=True,
            )
            db.session.add(artikel)
            db.session.commit()
            flash(f'Artikel "{artikel.bezeichnung}" erstellt.', 'success')
            return redirect(url_for('lager.index'))
        except Exception as e:
            db.session.rollback()
            flash('Fehler beim Erstellen des Artikels.', 'danger')
    
    return render_template('lager/artikel_form.html', artikel=None)


@lager_bp.route('/artikel/<int:id>')
@login_required
def detail(id):
    """Artikel-Detail + Lagerbewegungen."""
    artikel = LagerArtikel.query.get_or_404(id)
    bewegungen = artikel.bewegungen.order_by(LagerBewegung.datum.desc()).all()
    return render_template('lager/artikel_detail.html', artikel=artikel, bewegungen=bewegungen)


@lager_bp.route('/artikel/<int:id>/bewegung', methods=['POST'])
@login_required
def add_bewegung(id):
    """Lagerbewegung hinzufügen."""
    artikel = LagerArtikel.query.get_or_404(id)
    
    try:
        menge = float(request.form.get('menge', 0))
        typ = request.form.get('typ', 'eingang')
        
        # Bestand aktualisieren
        if typ == 'eingang':
            artikel.aktueller_bestand += menge
        else:
            artikel.aktueller_bestand -= menge
        
        bewegung = LagerBewegung(
            artikel_id=id,
            datum=datetime.now(),
            typ=typ,
            menge=menge,
            grund=request.form.get('grund', '').strip() or None,
            notiz=request.form.get('notiz', '').strip() or None,
            benutzer_id=1,  # TODO: current_user.id
            beleg_nummer=request.form.get('beleg_nummer', '').strip() or None,
        )
        db.session.add(bewegung)
        db.session.commit()
        flash(f'Lagerbewegung {typ} eingegeben ({menge} {artikel.einheit}).', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Fehler beim Eingeben der Lagerbewegung.', 'danger')
    
    return redirect(url_for('lager.detail', id=id))
