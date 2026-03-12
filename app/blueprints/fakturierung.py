from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, make_response, session
from flask_login import login_required, current_user

from app.extensions import db
from app.models.betrieb import Betrieb
from app.models.buchhaltung import Konto
from app.models.fakturierung import Kunde, Faktura, FAKTURA_ARTEN, FAKTURA_STATUS, GUTSCHRIFT_ARTEN
from app.services.fakturierung_service import (
    faktura_erstellen,
    faktura_als_bezahlt_markieren,
    faktura_stornieren,
    faktura_aus_vorlage,
    faktura_pdf,
    gutschrift_erstellen,
    gutschrift_empfaenger_sicherstellen,
    ART_HABEN_KONTO,
    FORDERUNG_KONTO_NR,
)

fakturierung_bp = Blueprint('fakturierung', __name__, url_prefix='/fakturierung')


def _gem_context():
    betrieb = Betrieb.query.first()
    return SimpleNamespace(
        id=1,
        name=betrieb.name if betrieb and betrieb.name else 'AgroBetrieb',
        aktuelles_geschaeftsjahr=_aktives_gj(),
    )


def _aktives_gj():
    return session.get('gj') or date.today().year


@fakturierung_bp.route('/')
@login_required
def liste():
    gem = _gem_context()
    jahr = request.args.get('jahr', type=int) or _aktives_gj()
    status_filter = request.args.get('status', '')
    art_filter = request.args.get('art', '')

    query = Faktura.query.filter_by(ist_vorlage=False, dokument_typ='rechnung')
    if jahr:
        query = query.filter_by(geschaeftsjahr=jahr)
    if status_filter:
        query = query.filter_by(status=status_filter)
    if art_filter:
        query = query.filter_by(art=art_filter)

    fakturen = query.order_by(Faktura.datum.desc()).all()
    jahre = [row[0] for row in db.session.query(Faktura.geschaeftsjahr).filter_by(ist_vorlage=False).distinct().order_by(Faktura.geschaeftsjahr.desc()).all()]
    if jahr not in jahre:
        jahre.insert(0, jahr)

    return render_template(
        'fakturierung/liste.html',
        gem=gem,
        gemeinschaften=[],
        fakturen=fakturen,
        summe_gesamt=sum(f.betrag_netto for f in fakturen),
        summe_offen=sum(f.betrag_netto for f in fakturen if f.ist_offen),
        aktuelles_jahr=jahr,
        verfuegbare_jahre=jahre,
        status_filter=status_filter,
        art_filter=art_filter,
        faktura_arten=FAKTURA_ARTEN,
        faktura_status=FAKTURA_STATUS,
        today=date.today(),
    )


@fakturierung_bp.route('/neu', methods=['GET', 'POST'])
@fakturierung_bp.route('/rechnung/new', methods=['GET', 'POST'])
@login_required
def neu():
    gem = _gem_context()
    kunden = Kunde.query.filter_by(aktiv=True).order_by(Kunde.name).all()
    haben_konten = Konto.query.filter(Konto.kontenklasse == 7, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    forderung_konten = Konto.query.filter(Konto.kontenklasse == 2, Konto.aktiv == True).order_by(Konto.kontonummer).all()

    if request.method == 'POST':
        try:
            positionen_daten = _positionen_aus_formular(request.form)
            if not positionen_daten:
                raise ValueError('Mindestens eine Position erforderlich.')
            datum = date.fromisoformat(request.form['datum'])
            faktura = faktura_erstellen(
                kunde_id=request.form.get('kunde_id', type=int),
                geschaeftsjahr=datum.year,
                art=request.form.get('art'),
                datum=datum,
                positionen_daten=positionen_daten,
                haben_konto_id=request.form.get('haben_konto_id', type=int) or None,
                forderung_konto_id=request.form.get('forderung_konto_id', type=int) or None,
                betreff=request.form.get('betreff', '').strip() or None,
                faellig_am=date.fromisoformat(request.form['faellig_am']) if request.form.get('faellig_am') else datum + timedelta(days=14),
                notizen=request.form.get('notizen', '').strip() or None,
                erstellt_von=current_user.id,
                ist_vorlage=request.form.get('ist_vorlage') == '1',
                vorlage_name=request.form.get('vorlage_name', '').strip() or None,
            )
            if faktura.ist_vorlage:
                flash('Vorlage gespeichert.', 'success')
                return redirect(url_for('fakturierung.vorlagen'))
            flash(f'Rechnung {faktura.fakturanummer} erstellt.', 'success')
            return redirect(url_for('fakturierung.detail', id=faktura.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), 'danger')

    heute = date.today()
    return render_template(
        'fakturierung/neu.html',
        gem=gem,
        kunden=kunden,
        haben_konten=haben_konten,
        forderung_konten=forderung_konten,
        faktura_arten=FAKTURA_ARTEN,
        art_haben_konto=ART_HABEN_KONTO,
        heute=heute.isoformat(),
        faellig_default=(heute + timedelta(days=14)).isoformat(),
    )


@fakturierung_bp.route('/<int:id>')
@fakturierung_bp.route('/rechnung/<int:id>')
@login_required
def detail(id):
    gem = _gem_context()
    faktura = Faktura.query.get_or_404(id)
    bank_konten = Konto.query.filter(Konto.kontenklasse == 3, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    return render_template('fakturierung/detail.html', faktura=faktura, gem=gem, bank_konten=bank_konten, heute=date.today().isoformat())


@fakturierung_bp.route('/<int:id>/pdf')
@login_required
def pdf(id):
    faktura = Faktura.query.get_or_404(id)
    response = make_response(faktura_pdf(id))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'inline; filename="{("Gutschrift" if faktura.ist_gutschrift else "Rechnung")}_{faktura.fakturanummer}.pdf"'
    return response


@fakturierung_bp.route('/<int:id>/bezahlt', methods=['POST'])
@login_required
def als_bezahlt(id):
    faktura = Faktura.query.get_or_404(id)
    try:
        faktura_als_bezahlt_markieren(
            id,
            date.fromisoformat(request.form.get('bezahlt_datum', date.today().isoformat())),
            request.form.get('bank_konto_id', type=int),
            current_user.id,
        )
        flash(f'Rechnung {faktura.fakturanummer} als bezahlt markiert.', 'success')
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    return redirect(url_for('fakturierung.detail', id=id))


@fakturierung_bp.route('/<int:id>/stornieren', methods=['POST'])
@login_required
def stornieren(id):
    faktura = Faktura.query.get_or_404(id)
    try:
        faktura_stornieren(id, current_user.id)
        flash(f'Rechnung {faktura.fakturanummer} storniert.', 'warning')
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
    return redirect(url_for('fakturierung.detail', id=id))


@fakturierung_bp.route('/vorlagen')
@login_required
def vorlagen():
    gem = _gem_context()
    return render_template('fakturierung/vorlagen.html', gem=gem, gemeinschaften=[], vorlagen=Faktura.query.filter_by(ist_vorlage=True).order_by(Faktura.vorlage_name).all(), faktura_arten=FAKTURA_ARTEN, heute=date.today().isoformat())


@fakturierung_bp.route('/vorlagen/<int:id>/erstellen', methods=['POST'])
@login_required
def vorlage_erstellen(id):
    try:
        datum = date.fromisoformat(request.form.get('datum', date.today().isoformat()))
        neue_faktura = faktura_aus_vorlage(id, datum, datum.year, current_user.id)
        flash(f'Rechnung {neue_faktura.fakturanummer} aus Vorlage erstellt.', 'success')
        return redirect(url_for('fakturierung.detail', id=neue_faktura.id))
    except Exception as exc:
        db.session.rollback()
        flash(str(exc), 'danger')
        return redirect(url_for('fakturierung.vorlagen'))


@fakturierung_bp.route('/<int:id>/gutschrift', methods=['GET', 'POST'])
@login_required
def gutschrift_aus_rechnung(id):
    gem = _gem_context()
    rechnung = Faktura.query.get_or_404(id)
    haben_konten = Konto.query.filter(Konto.kontenklasse == 7, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    forderung_konten = Konto.query.filter(Konto.kontenklasse == 2, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    kunden = Kunde.query.filter_by(aktiv=True).order_by(Kunde.name).all()
    if request.method == 'POST':
        try:
            positionen_daten = _positionen_aus_formular(request.form)
            gs = gutschrift_erstellen(
                kunde_id=rechnung.kunde_id,
                geschaeftsjahr=request.form.get('geschaeftsjahr', type=int) or date.today().year,
                art=rechnung.art,
                datum=date.fromisoformat(request.form['datum']),
                positionen_daten=positionen_daten,
                haben_konto_id=request.form.get('haben_konto_id', type=int) or rechnung.haben_konto_id,
                forderung_konto_id=request.form.get('forderung_konto_id', type=int) or rechnung.forderung_konto_id,
                betreff=request.form.get('betreff', '').strip() or None,
                notizen=request.form.get('notizen', '').strip() or None,
                erstellt_von=current_user.id,
                storno_von_id=rechnung.id,
            )
            flash(f'Gutschrift {gs.fakturanummer} erstellt.', 'success')
            return redirect(url_for('fakturierung.detail', id=gs.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), 'danger')

    return render_template('fakturierung/gutschrift_neu.html', gem=gem, rechnung=rechnung, haben_konten=haben_konten, forderung_konten=forderung_konten, kunden=kunden, faktura_arten=FAKTURA_ARTEN, art_haben_konto=ART_HABEN_KONTO, heute=date.today().isoformat())


@fakturierung_bp.route('/gutschriften')
@login_required
def gutschriften_liste():
    gem = _gem_context()
    jahr = request.args.get('jahr', type=int) or _aktives_gj()
    status_filter = request.args.get('status', '')
    query = Faktura.query.filter_by(dokument_typ='gutschrift', ist_vorlage=False)
    if jahr:
        query = query.filter_by(geschaeftsjahr=jahr)
    if status_filter:
        query = query.filter_by(status=status_filter)
    gutschriften = query.order_by(Faktura.datum.desc()).all()
    jahre = [row[0] for row in db.session.query(Faktura.geschaeftsjahr).filter_by(dokument_typ='gutschrift', ist_vorlage=False).distinct().order_by(Faktura.geschaeftsjahr.desc()).all()]
    if jahr not in jahre:
        jahre.insert(0, jahr)
    return render_template('fakturierung/gutschriften_liste.html', gem=gem, gemeinschaften=[], gutschriften=gutschriften, summe_gesamt=sum(g.betrag_netto for g in gutschriften), aktuelles_jahr=jahr, verfuegbare_jahre=jahre, status_filter=status_filter, faktura_status=FAKTURA_STATUS, today=date.today())


def _positionen_aus_formular(request_form):
    bezeichnungen = request_form.getlist('pos_bezeichnung')
    mengen = request_form.getlist('pos_menge')
    einheiten = request_form.getlist('pos_einheit')
    einzelpreise = request_form.getlist('pos_einzelpreis')
    betraege = request_form.getlist('pos_betrag')

    positionen_daten = []
    for index, bezeichnung in enumerate(bezeichnungen):
        bezeichnung = bezeichnung.strip()
        if not bezeichnung:
            continue
        menge = None
        if index < len(mengen) and mengen[index].strip():
            try:
                menge = Decimal(mengen[index].strip().replace(',', '.'))
            except InvalidOperation:
                menge = None
        einzelpreis = None
        if index < len(einzelpreise) and einzelpreise[index].strip():
            try:
                einzelpreis = Decimal(einzelpreise[index].strip().replace(',', '.'))
            except InvalidOperation:
                einzelpreis = None
        if menge is not None and einzelpreis is not None:
            betrag = menge * einzelpreis
        else:
            try:
                betrag = Decimal((betraege[index] if index < len(betraege) else '0').strip().replace(',', '.'))
            except InvalidOperation:
                betrag = Decimal('0')
        positionen_daten.append({
            'bezeichnung': bezeichnung,
            'menge': menge,
            'einheit': einheiten[index].strip() if index < len(einheiten) else None,
            'einzelpreis': einzelpreis,
            'betrag': betrag,
            'sortierung': index,
        })
    return positionen_daten


@fakturierung_bp.route('/gutschrift/neu', methods=['GET', 'POST'])
@login_required
def gutschrift_neu():
    gem = _gem_context()
    kunden = Kunde.query.filter_by(aktiv=True).order_by(Kunde.name).all()
    haben_konten = Konto.query.filter(Konto.kontenklasse == 7, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    verbindlichkeit_konten = Konto.query.filter(Konto.kontenklasse == 2, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    if request.method == 'POST':
        try:
            kunde_id = gutschrift_empfaenger_sicherstellen(
                empfaenger_typ=request.form.get('empfaenger_typ', 'kunde'),
                kunde_id=request.form.get('kunde_id', type=int),
                name=request.form.get('dritter_name'),
                adresse=request.form.get('dritter_adresse'),
                ort=request.form.get('dritter_ort'),
                plz=request.form.get('dritter_plz'),
                iban=request.form.get('dritter_iban'),
            )
            gs = gutschrift_erstellen(
                kunde_id=kunde_id,
                geschaeftsjahr=request.form.get('geschaeftsjahr', type=int) or date.today().year,
                art=request.form.get('art', 'sonstiges'),
                datum=date.fromisoformat(request.form['datum']),
                positionen_daten=_positionen_aus_formular(request.form),
                haben_konto_id=request.form.get('haben_konto_id', type=int) or None,
                forderung_konto_id=request.form.get('forderung_konto_id', type=int) or None,
                betreff=request.form.get('betreff', '').strip() or None,
                notizen=request.form.get('notizen', '').strip() or None,
                erstellt_von=current_user.id,
            )
            db.session.commit()
            flash(f'Gutschrift {gs.fakturanummer} erstellt.', 'success')
            return redirect(url_for('fakturierung.detail', id=gs.id))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
    return render_template('fakturierung/gutschrift_neu.html', gem=gem, rechnung=None, haben_konten=haben_konten, verbindlichkeit_konten=verbindlichkeit_konten, kunden=kunden, faktura_arten=GUTSCHRIFT_ARTEN, art_haben_konto=ART_HABEN_KONTO, heute=date.today().isoformat())


@fakturierung_bp.route('/kunden')
@login_required
def kunden():
    gem = _gem_context()
    return render_template('fakturierung/kunden.html', gem=gem, gemeinschaften=[], kunden=Kunde.query.order_by(Kunde.name).all())


@fakturierung_bp.route('/kunden/neu', methods=['GET', 'POST'])
@fakturierung_bp.route('/kunde/new', methods=['GET', 'POST'])
@login_required
def kunde_neu():
    gem = _gem_context()
    konten_klasse2 = Konto.query.filter(Konto.kontenklasse == 2, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    if request.method == 'POST':
        try:
            kunde = Kunde(
                name=request.form.get('name', '').strip(),
                adresse=request.form.get('adresse', '').strip() or request.form.get('strasse', '').strip() or None,
                plz=request.form.get('plz', '').strip() or None,
                ort=request.form.get('ort', '').strip() or None,
                uid_nummer=request.form.get('uid_nummer', '').strip() or None,
                email=request.form.get('email', '').strip() or None,
                telefon=request.form.get('telefon', '').strip() or None,
                iban=request.form.get('iban', '').strip() or None,
                notizen=request.form.get('notizen', '').strip() or None,
                konto_id=request.form.get('konto_id', type=int) or None,
            )
            db.session.add(kunde)
            db.session.commit()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': f'Kunde "{kunde.name}" erstellt.'})
            flash(f'Kunde "{kunde.name}" erstellt.', 'success')
            return redirect(url_for('fakturierung.kunden'))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': str(exc)}), 400
    return render_template('fakturierung/kunde_form.html', gem=gem, kunde=None, konten_klasse2=konten_klasse2)


@fakturierung_bp.route('/kunden/<int:id>/bearbeiten', methods=['GET', 'POST'])
@login_required
def kunde_bearbeiten(id):
    gem = _gem_context()
    kunde = Kunde.query.get_or_404(id)
    konten_klasse2 = Konto.query.filter(Konto.kontenklasse == 2, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    if request.method == 'POST':
        try:
            kunde.name = request.form.get('name', '').strip()
            kunde.adresse = request.form.get('adresse', '').strip() or request.form.get('strasse', '').strip() or None
            kunde.plz = request.form.get('plz', '').strip() or None
            kunde.ort = request.form.get('ort', '').strip() or None
            kunde.uid_nummer = request.form.get('uid_nummer', '').strip() or None
            kunde.email = request.form.get('email', '').strip() or None
            kunde.telefon = request.form.get('telefon', '').strip() or None
            kunde.iban = request.form.get('iban', '').strip() or None
            kunde.notizen = request.form.get('notizen', '').strip() or None
            kunde.konto_id = request.form.get('konto_id', type=int) or None
            kunde.aktiv = request.form.get('aktiv') == '1' or 'aktiv' in request.form
            db.session.commit()
            flash(f'Kunde "{kunde.name}" gespeichert.', 'success')
            return redirect(url_for('fakturierung.kunden'))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
    return render_template('fakturierung/kunde_form.html', gem=gem, kunde=kunde, konten_klasse2=konten_klasse2)
