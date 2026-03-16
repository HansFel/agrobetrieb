import base64
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace

from flask import Blueprint, render_template, redirect, url_for, flash, request, Response, session
from flask_login import login_required, current_user

from app.extensions import db
from app.models.betrieb import Betrieb
from app.models.buchhaltung import Konto, KontoSaldo, Buchung, Buchungsschluessel, BankImportConfig
from app.services.bank_import_service import csv_vorschau, csv_importieren
from app.services.buchung_service import (
    buchung_erstellen,
    sammelbuchung_erstellen,
    buchung_stornieren as buchung_stornieren_service,
    gegenkonto_aendern,
    bilanz_berechnen,
    guv_berechnen,
)
from app.services.kontenplan_service import KLASSEN_NAMEN, standard_kontenplan_erstellen

buchhaltung_bp = Blueprint('buchhaltung', __name__, url_prefix='/buchhaltung')


def _betrieb_obj():
    return Betrieb.query.first()


def _gem_context():
    betrieb = _betrieb_obj()
    return SimpleNamespace(
        id=1,
        name=betrieb.name if betrieb and betrieb.name else 'AgroBetrieb',
        aktuelles_geschaeftsjahr=_aktives_gj(),
    )


def _aktives_gj():
    return session.get('gj') or date.today().year


def _gemeinschaften():
    return []


@buchhaltung_bp.route('/geschaeftsjahr-setzen', methods=['POST'])
@login_required
def geschaeftsjahr_setzen():
    gj = request.form.get('geschaeftsjahr', type=int)
    next_url = request.form.get('next') or url_for('buchhaltung.journal')
    echtes_gj = date.today().year

    if gj and gj != echtes_gj:
        session['gj'] = gj
        flash(f'Geschäftsjahr auf {gj} fixiert.', 'warning')
    else:
        session.pop('gj', None)
        flash('Geschäftsjahr-Fixierung aufgehoben.', 'success')

    return redirect(next_url)


@buchhaltung_bp.route('/')
@login_required
def index():
    return redirect(url_for('buchhaltung.journal'))


@buchhaltung_bp.route('/kontenplan')
@login_required
def kontenplan():
    gem = _gem_context()
    konten = Konto.query.order_by(Konto.kontenklasse, Konto.kontonummer).all()
    klassen = {}
    for konto in konten:
        klassen.setdefault(konto.kontenklasse, {
            'nummer': konto.kontenklasse,
            'name': KLASSEN_NAMEN.get(konto.kontenklasse, f'Klasse {konto.kontenklasse}'),
            'konten': [],
        })
        klassen[konto.kontenklasse]['konten'].append(konto)

    return render_template('buchhaltung/kontenplan.html', gem=gem, klassen=klassen, gemeinschaften=_gemeinschaften())


@buchhaltung_bp.route('/konto/neu', methods=['GET', 'POST'])
@login_required
def konto_neu():
    gem = _gem_context()
    if request.method == 'POST':
        kontonummer = request.form.get('kontonummer', '').strip()
        bezeichnung = request.form.get('bezeichnung', '').strip()
        kontenklasse = request.form.get('kontenklasse', type=int)
        kontotyp = request.form.get('kontotyp', '').strip()

        if not kontonummer or not bezeichnung or kontenklasse is None or not kontotyp:
            flash('Bitte alle Pflichtfelder ausfüllen.', 'danger')
            return render_template('buchhaltung/konto_form.html', gem=gem, konto=None, neu=True)

        if Konto.query.filter_by(kontonummer=kontonummer).first():
            flash(f'Kontonummer {kontonummer} existiert bereits.', 'danger')
            return render_template('buchhaltung/konto_form.html', gem=gem, konto=None, neu=True)

        konto = Konto(
            kontonummer=kontonummer,
            bezeichnung=bezeichnung,
            kontenklasse=kontenklasse,
            kontotyp=kontotyp,
            jahresuebertrag='jahresuebertrag' in request.form,
            ist_sammelkonto='ist_sammelkonto' in request.form,
            ist_importkonto='ist_importkonto' in request.form,
            aktiv='aktiv' in request.form or True,
        )
        db.session.add(konto)
        db.session.commit()
        flash(f'Konto {kontonummer} angelegt.', 'success')
        return redirect(url_for('buchhaltung.kontenplan'))

    return render_template('buchhaltung/konto_form.html', gem=gem, konto=None, neu=True)


@buchhaltung_bp.route('/konto/<int:konto_id>', methods=['GET', 'POST'])
@login_required
def konto_bearbeiten(konto_id):
    gem = _gem_context()
    konto = Konto.query.get_or_404(konto_id)

    if request.method == 'POST':
        konto.bezeichnung = request.form.get('bezeichnung', '').strip()
        konto.kontotyp = request.form.get('kontotyp', '').strip()
        konto.jahresuebertrag = 'jahresuebertrag' in request.form
        konto.ist_sammelkonto = 'ist_sammelkonto' in request.form
        konto.ist_importkonto = 'ist_importkonto' in request.form
        konto.aktiv = 'aktiv' in request.form
        db.session.commit()
        flash(f'Konto {konto.kontonummer} aktualisiert.', 'success')
        return redirect(url_for('buchhaltung.kontenplan'))

    return render_template('buchhaltung/konto_form.html', gem=gem, konto=konto, neu=False)


@buchhaltung_bp.route('/konten/standard-anlegen', methods=['POST'])
@login_required
def standard_kontenplan_anlegen():
    anzahl = standard_kontenplan_erstellen()
    flash(f'{anzahl} Standard-Konten angelegt.' if anzahl else 'Alle Standard-Konten sind bereits vorhanden.', 'success' if anzahl else 'info')
    return redirect(url_for('buchhaltung.kontenplan'))


@buchhaltung_bp.route('/salden')
@login_required
def saldenliste():
    gem = _gem_context()
    geschaeftsjahr = request.args.get('jahr', type=int) or _aktives_gj()
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontenklasse, Konto.kontonummer).all()
    konto_ids = [konto.id for konto in konten]
    salden_map = {}
    if konto_ids:
        salden_map = {
            saldo.konto_id: saldo
            for saldo in KontoSaldo.query.filter(
                KontoSaldo.konto_id.in_(konto_ids),
                KontoSaldo.geschaeftsjahr == geschaeftsjahr,
            ).all()
        }

    klassen = {}
    for konto in konten:
        klasse = konto.kontenklasse
        klassen.setdefault(klasse, {
            'nummer': klasse,
            'name': KLASSEN_NAMEN.get(klasse, f'Klasse {klasse}'),
            'zeilen': [],
            'summe_soll': Decimal('0'),
            'summe_haben': Decimal('0'),
            'summe_saldo': Decimal('0'),
        })
        saldo = salden_map.get(konto.id)
        zeile = {
            'konto': konto,
            'saldo_beginn': saldo.saldo_beginn if saldo else Decimal('0'),
            'summe_soll': saldo.summe_soll if saldo else Decimal('0'),
            'summe_haben': saldo.summe_haben if saldo else Decimal('0'),
            'saldo_aktuell': saldo.saldo_aktuell if saldo else Decimal('0'),
        }
        klassen[klasse]['zeilen'].append(zeile)
        klassen[klasse]['summe_soll'] += zeile['summe_soll']
        klassen[klasse]['summe_haben'] += zeile['summe_haben']
        klassen[klasse]['summe_saldo'] += zeile['saldo_aktuell']

    return render_template('buchhaltung/saldenliste.html', gem=gem, klassen=klassen, geschaeftsjahr=geschaeftsjahr, gemeinschaften=_gemeinschaften())


@buchhaltung_bp.route('/buchung/new', methods=['GET', 'POST'])
@buchhaltung_bp.route('/buchung/neu', methods=['GET', 'POST'])
@login_required
def buchung_neu():
    gem = _gem_context()
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    schluessel = Buchungsschluessel.query.filter_by(aktiv=True).order_by(Buchungsschluessel.sortierung, Buchungsschluessel.kuerzel).all()

    if request.method == 'POST':
        try:
            buchung = buchung_erstellen(
                geschaeftsjahr=request.form.get('geschaeftsjahr', type=int) or _aktives_gj(),
                datum=date.fromisoformat(request.form['datum']),
                soll_konto_id=request.form.get('soll_konto_id', type=int),
                haben_konto_id=request.form.get('haben_konto_id', type=int),
                betrag=Decimal(request.form['betrag'].replace(',', '.')),
                buchungstext=request.form.get('buchungstext', '').strip(),
                erstellt_von=current_user.id,
                beleg_nummer=request.form.get('beleg_nummer', '').strip() or None,
                beleg_datum=date.fromisoformat(request.form['beleg_datum']) if request.form.get('beleg_datum') else None,
            )
            flash(f'Buchung {buchung.buchungsnummer} erfasst.', 'success')
            return redirect(url_for('buchhaltung.journal'))
        except Exception as exc:
            flash(str(exc), 'danger')

    echtes_gj = date.today().year
    aktuelles_gj = _aktives_gj()
    gj_optionen = list(range(echtes_gj - 3, echtes_gj + 2))
    return render_template(
        'buchhaltung/buchung_neu.html',
        gem=gem,
        konten=konten,
        schluessel=schluessel,
        gemeinschaften=_gemeinschaften(),
        heute=date.today().isoformat(),
        aktuelles_gj=aktuelles_gj,
        echtes_gj=echtes_gj,
        gj_fixiert=aktuelles_gj != echtes_gj,
        gj_optionen=gj_optionen,
        verfuegbare_jahre=gj_optionen,
    )


@buchhaltung_bp.route('/buchung/sammel-neu', methods=['GET', 'POST'])
@login_required
def buchung_sammel_neu():
    gem = _gem_context()
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()

    if request.method == 'POST':
        try:
            zeilen = []
            index = 0
            while True:
                konto_key = f'konto_{index}'
                if konto_key not in request.form:
                    break
                konto_id = request.form.get(konto_key, '').strip()
                betrag = request.form.get(f'betrag_{index}', '').strip().replace(',', '.')
                text = request.form.get(f'text_{index}', '').strip()
                if konto_id and betrag:
                    zeilen.append({'konto_id': int(konto_id), 'betrag': Decimal(betrag), 'text': text})
                index += 1

            buchungen = sammelbuchung_erstellen(
                geschaeftsjahr=request.form.get('geschaeftsjahr', type=int) or _aktives_gj(),
                datum=date.fromisoformat(request.form['datum']),
                gegenkonto_id=request.form.get('gegenkonto_id', type=int),
                zeilen=zeilen,
                beleg_nummer=request.form.get('beleg_nummer', '').strip() or None,
                erstellt_von=current_user.id,
                richtung=request.form.get('richtung', 'ausgabe'),
                beleg_datum=date.fromisoformat(request.form['beleg_datum']) if request.form.get('beleg_datum') else None,
            )
            flash(f'{len(buchungen)} Buchungen erfasst.', 'success')
            return redirect(url_for('buchhaltung.journal'))
        except Exception as exc:
            flash(str(exc), 'danger')

    echtes_gj = date.today().year
    aktuelles_gj = _aktives_gj()
    gj_optionen = list(range(echtes_gj - 3, echtes_gj + 2))
    return render_template(
        'buchhaltung/buchung_sammel_neu.html',
        gem=gem,
        konten=konten,
        gemeinschaften=_gemeinschaften(),
        heute=date.today().isoformat(),
        aktuelles_gj=aktuelles_gj,
        echtes_gj=echtes_gj,
        gj_fixiert=aktuelles_gj != echtes_gj,
        gj_optionen=gj_optionen,
    )


@buchhaltung_bp.route('/konto')
@login_required
def konten():
    return redirect(url_for('buchhaltung.kontenplan'))


@buchhaltung_bp.route('/buchung/<int:buchung_id>/stornieren', methods=['POST'])
@login_required
def buchung_stornieren(buchung_id):
    buchung = Buchung.query.get_or_404(buchung_id)
    try:
        buchung_stornieren_service(buchung.id, current_user.id, request.form.get('grund', '').strip())
        flash(f'Buchung {buchung.buchungsnummer} storniert.', 'success')
    except Exception as exc:
        flash(str(exc), 'danger')
    return redirect(url_for('buchhaltung.journal'))


@buchhaltung_bp.route('/buchung/<int:buchung_id>/umbuchen', methods=['GET', 'POST'])
@login_required
def buchung_umbuchen(buchung_id):
    gem = _gem_context()
    buchung = Buchung.query.get_or_404(buchung_id)
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    schluessel = Buchungsschluessel.query.filter_by(aktiv=True).order_by(Buchungsschluessel.sortierung).all()

    if request.method == 'POST':
        try:
            neues_soll_id = request.form.get('soll_konto_id', type=int)
            neues_haben_id = request.form.get('haben_konto_id', type=int)
            neuer_text = request.form.get('buchungstext', buchung.buchungstext).strip()
            buchung_stornieren_service(buchung.id, current_user.id, 'Umkontierung')
            buchung_erstellen(
                geschaeftsjahr=buchung.geschaeftsjahr,
                datum=buchung.datum,
                soll_konto_id=neues_soll_id,
                haben_konto_id=neues_haben_id,
                betrag=buchung.betrag,
                buchungstext=neuer_text,
                erstellt_von=current_user.id,
                beleg_nummer=buchung.beleg_nummer,
                buchungsart='manuell',
            )
            flash(f'Buchung {buchung.buchungsnummer} umgebucht.', 'success')
            return redirect(url_for('buchhaltung.journal'))
        except Exception as exc:
            flash(str(exc), 'danger')

    return render_template('buchhaltung/buchung_umbuchen.html', gem=gem, buchung=buchung, konten=konten, schluessel=schluessel)


@buchhaltung_bp.route('/buchung/<int:buchung_id>/splitten', methods=['GET', 'POST'])
@login_required
def buchung_splitten(buchung_id):
    """Splitbuchung: Eine Buchung auf mehrere Kostenstellen verteilen.

    Das Bankkonto / Importkonto bleibt immer fix als Gegenkonto.
    Bei Import-Buchungen wird die Forderung/Verbindlichkeit auf
    mehrere Kostenstellen aufgeteilt.
    """
    gem = _gem_context()
    buchung = Buchung.query.get_or_404(buchung_id)

    if buchung.storniert:
        flash('Stornierte Buchungen können nicht gesplittet werden.', 'danger')
        return redirect(url_for('buchhaltung.journal'))

    soll_konto = db.session.get(Konto, buchung.soll_konto_id)
    haben_konto = db.session.get(Konto, buchung.haben_konto_id)

    # Bei Import-Buchungen: Bank ist eine Seite, das Gegenkonto (Forderung/Verbindlichkeit)
    # die andere. Der Split geht VOM Gegenkonto (Klasse 2) aus – das bleibt fix.
    # Die Zeilen verteilen den Betrag auf Kostenstellen (Klasse 4/5/6/7/8).
    soll_ist_bank = soll_konto and (soll_konto.ist_importkonto or soll_konto.kontenklasse == 3)
    haben_ist_bank = haben_konto and (haben_konto.ist_importkonto or haben_konto.kontenklasse == 3)

    if soll_ist_bank and haben_konto:
        # Bank im Soll, Forderung/Verbindlichkeit im Haben → fix: Haben-Konto
        # Ausgabe: Kostenstellen im Soll (anstatt Forderung)
        gegenkonto_id = buchung.haben_konto_id
        richtung = 'einnahme'   # Gegenkonto im Haben, Zeilen im Soll
        gegenkonto_fix = True
        fix_konto = haben_konto
    elif haben_ist_bank and soll_konto:
        # Bank im Haben, Forderung/Verbindlichkeit im Soll → fix: Soll-Konto
        # Einnahme: Kostenstellen im Haben (anstatt Verbindlichkeit)
        gegenkonto_id = buchung.soll_konto_id
        richtung = 'ausgabe'    # Gegenkonto im Soll, Zeilen im Haben
        gegenkonto_fix = True
        fix_konto = soll_konto
    else:
        # Kein Bankkonto erkannt – manuell wählbar
        gegenkonto_id = buchung.haben_konto_id
        richtung = 'ausgabe'
        gegenkonto_fix = False
        fix_konto = haben_konto

    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    # Kostenstellen-Konten: alle außer dem fixen Gegenkonto
    kostenstellen_konten = [k for k in konten if k.id != gegenkonto_id]

    if request.method == 'POST':
        try:
            if not gegenkonto_fix:
                override_gegenkonto = request.form.get('gegenkonto_id', type=int)
                if override_gegenkonto:
                    gegenkonto_id = override_gegenkonto
                richtung = request.form.get('richtung', richtung)

            zeilen = []
            index = 0
            while True:
                if f'konto_{index}' not in request.form:
                    break
                konto_id = request.form.get(f'konto_{index}', type=int)
                betrag_raw = request.form.get(f'betrag_{index}', '').strip().replace(',', '.')
                text = request.form.get(f'text_{index}', '').strip()
                if konto_id and betrag_raw:
                    zeilen.append({'konto_id': konto_id, 'betrag': Decimal(betrag_raw), 'text': text})
                index += 1

            if not zeilen:
                raise ValueError('Mindestens eine Split-Zeile erforderlich.')

            summe = sum(z['betrag'] for z in zeilen)
            if abs(summe - buchung.betrag) > Decimal('0.01'):
                raise ValueError(
                    f'Summe der Teilbeträge ({summe:.2f} €) stimmt nicht mit '
                    f'Originalbetrag ({buchung.betrag:.2f} €) überein.'
                )

            # Ursprungsbuchung bleibt unverändert – nur neue Weiter-Buchungen erstellen
            neue = sammelbuchung_erstellen(
                geschaeftsjahr=buchung.geschaeftsjahr,
                datum=buchung.datum,
                gegenkonto_id=gegenkonto_id,
                zeilen=zeilen,
                beleg_nummer=buchung.beleg_nummer,
                erstellt_von=current_user.id,
                richtung=richtung,
                beleg_datum=buchung.beleg_datum,
            )
            flash(f'{len(neue)} Weiterbuchungen von {buchung.buchungsnummer} auf Kostenstellen erstellt.', 'success')
            return redirect(url_for('buchhaltung.journal'))
        except Exception as exc:
            db.session.rollback()
            flash(str(exc), 'danger')

    return render_template(
        'buchhaltung/buchung_splitten.html',
        gem=gem,
        buchung=buchung,
        konten=kostenstellen_konten,
        alle_konten=konten,
        gegenkonto_id=gegenkonto_id,
        gegenkonto_fix=gegenkonto_fix,
        fix_konto=fix_konto,
        richtung=richtung,
        gemeinschaften=_gemeinschaften(),
    )


@buchhaltung_bp.route('/buchung/<int:buchung_id>/gegenkonto-aendern', methods=['GET', 'POST'])
@login_required
def buchung_gegenkonto_aendern(buchung_id):
    gem = _gem_context()
    buchung = Buchung.query.get_or_404(buchung_id)
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    soll_konto = db.session.get(Konto, buchung.soll_konto_id)
    haben_konto = db.session.get(Konto, buchung.haben_konto_id)
    soll_ist_bank = soll_konto and (soll_konto.ist_importkonto or soll_konto.kontenklasse == 3)
    bank_konto = soll_konto if soll_ist_bank else haben_konto
    aktuelles_gegenkonto_id = buchung.haben_konto_id if soll_ist_bank else buchung.soll_konto_id

    if request.method == 'POST':
        try:
            gegenkonto_aendern(buchung.id, request.form.get('gegenkonto_id', type=int))
            flash(f'Gegenkonto der Buchung {buchung.buchungsnummer} geändert.', 'success')
            return redirect(url_for('buchhaltung.journal'))
        except Exception as exc:
            flash(str(exc), 'danger')

    schluessel = Buchungsschluessel.query.filter_by(aktiv=True).order_by(Buchungsschluessel.sortierung).all()
    return render_template(
        'buchhaltung/buchung_gegenkonto_aendern.html',
        gem=gem,
        buchung=buchung,
        konten=konten,
        schluessel=schluessel,
        bank_konto=bank_konto,
        aktuelles_gegenkonto_id=aktuelles_gegenkonto_id,
    )


@buchhaltung_bp.route('/journal')
@login_required
def journal():
    gem = _gem_context()
    geschaeftsjahr = request.args.get('jahr', type=int) or _aktives_gj()
    konto_filter = request.args.get('konto', type=int)
    buchungsart_filter = request.args.get('buchungsart', '')
    datum_von = request.args.get('datum_von', '')
    datum_bis = request.args.get('datum_bis', '')
    text_filter = request.args.get('text', '').strip()

    query = Buchung.query.filter_by(geschaeftsjahr=geschaeftsjahr)
    if konto_filter:
        query = query.filter(db.or_(Buchung.soll_konto_id == konto_filter, Buchung.haben_konto_id == konto_filter))
    if buchungsart_filter:
        query = query.filter_by(buchungsart=buchungsart_filter)
    if datum_von:
        query = query.filter(Buchung.datum >= date.fromisoformat(datum_von))
    if datum_bis:
        query = query.filter(Buchung.datum <= date.fromisoformat(datum_bis))
    if text_filter:
        query = query.filter(Buchung.buchungstext.ilike(f'%{text_filter}%'))

    buchungen = query.order_by(Buchung.datum.desc(), Buchung.id.desc()).all()
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    return render_template(
        'buchhaltung/journal.html',
        gem=gem,
        gemeinschaften=_gemeinschaften(),
        buchungen=buchungen,
        konten=konten,
        geschaeftsjahr=geschaeftsjahr,
        konto_filter=konto_filter,
        buchungsart_filter=buchungsart_filter,
        datum_von=datum_von,
        datum_bis=datum_bis,
        text_filter=text_filter,
    )


@buchhaltung_bp.route('/konto/<int:konto_id>/kontoblatt')
@login_required
def kontoblatt(konto_id):
    gem = _gem_context()
    geschaeftsjahr = request.args.get('jahr', type=int) or _aktives_gj()
    konto = Konto.query.get_or_404(konto_id)
    buchungen = Buchung.query.filter(
        Buchung.geschaeftsjahr == geschaeftsjahr,
        db.or_(Buchung.soll_konto_id == konto.id, Buchung.haben_konto_id == konto.id),
    ).order_by(Buchung.datum, Buchung.id).all()
    saldo = KontoSaldo.query.filter_by(konto_id=konto.id, geschaeftsjahr=geschaeftsjahr).first()
    return render_template('buchhaltung/kontoblatt.html', gem=gem, konto=konto, buchungen=buchungen, saldo=saldo, geschaeftsjahr=geschaeftsjahr)


@buchhaltung_bp.route('/bilanz')
@login_required
def bilanz():
    gem = _gem_context()
    geschaeftsjahr = request.args.get('jahr', type=int) or _aktives_gj()
    daten = bilanz_berechnen(geschaeftsjahr)
    return render_template('buchhaltung/bilanz.html', gem=gem, geschaeftsjahr=geschaeftsjahr, **daten)


@buchhaltung_bp.route('/guv')
@login_required
def guv():
    gem = _gem_context()
    geschaeftsjahr = request.args.get('jahr', type=int) or _aktives_gj()
    daten = guv_berechnen(geschaeftsjahr)
    return render_template('buchhaltung/guv.html', gem=gem, geschaeftsjahr=geschaeftsjahr, **daten)


@buchhaltung_bp.route('/buchungsschluessel')
@login_required
def buchungsschluessel_liste():
    gem = _gem_context()
    schluessel = Buchungsschluessel.query.order_by(Buchungsschluessel.sortierung, Buchungsschluessel.kuerzel).all()
    return render_template('buchhaltung/buchungsschluessel_liste.html', gem=gem, schluessel=schluessel, gemeinschaften=_gemeinschaften())


@buchhaltung_bp.route('/buchungsschluessel/neu', methods=['GET', 'POST'])
@login_required
def buchungsschluessel_neu():
    gem = _gem_context()
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    if request.method == 'POST':
        bs = Buchungsschluessel(
            kuerzel=request.form.get('kuerzel', '').strip(),
            bezeichnung=request.form.get('bezeichnung', '').strip(),
            buchungstext=request.form.get('buchungstext', '').strip() or None,
            soll_klassen=request.form.get('soll_klassen', '').strip() or None,
            haben_klassen=request.form.get('haben_klassen', '').strip() or None,
            soll_konto_id=request.form.get('soll_konto_id', type=int) or None,
            haben_konto_id=request.form.get('haben_konto_id', type=int) or None,
            suchbegriffe=request.form.get('suchbegriffe', '').strip() or None,
            sortierung=request.form.get('sortierung', type=int) or 0,
            aktiv='aktiv' in request.form,
        )
        db.session.add(bs)
        db.session.commit()
        flash('Buchungsschlüssel angelegt.', 'success')
        return redirect(url_for('buchhaltung.buchungsschluessel_liste'))
    # Suchbegriff aus Analyse-Modal vorausfüllen
    prefill_suchbegriff = request.args.get('suchbegriff', '')
    return render_template('buchhaltung/buchungsschluessel_form.html', gem=gem, bs=None, konten=konten,
                           prefill_suchbegriff=prefill_suchbegriff)


@buchhaltung_bp.route('/buchungsschluessel/<int:bs_id>', methods=['GET', 'POST'])
@login_required
def buchungsschluessel_bearbeiten(bs_id):
    gem = _gem_context()
    bs = Buchungsschluessel.query.get_or_404(bs_id)
    konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    if request.method == 'POST':
        bs.kuerzel = request.form.get('kuerzel', '').strip()
        bs.bezeichnung = request.form.get('bezeichnung', '').strip()
        bs.buchungstext = request.form.get('buchungstext', '').strip() or None
        bs.soll_klassen = request.form.get('soll_klassen', '').strip() or None
        bs.haben_klassen = request.form.get('haben_klassen', '').strip() or None
        bs.soll_konto_id = request.form.get('soll_konto_id', type=int) or None
        bs.haben_konto_id = request.form.get('haben_konto_id', type=int) or None
        bs.suchbegriffe = request.form.get('suchbegriffe', '').strip() or None
        bs.sortierung = request.form.get('sortierung', type=int) or 0
        bs.aktiv = 'aktiv' in request.form
        db.session.commit()
        flash('Buchungsschlüssel gespeichert.', 'success')
        return redirect(url_for('buchhaltung.buchungsschluessel_liste'))
    return render_template('buchhaltung/buchungsschluessel_form.html', gem=gem, bs=bs, konten=konten)


@buchhaltung_bp.route('/buchungsschluessel/<int:bs_id>/loeschen', methods=['POST'])
@login_required
def buchungsschluessel_loeschen(bs_id):
    bs = Buchungsschluessel.query.get_or_404(bs_id)
    db.session.delete(bs)
    db.session.commit()
    flash('Buchungsschlüssel gelöscht.', 'success')
    return redirect(url_for('buchhaltung.buchungsschluessel_liste'))


@buchhaltung_bp.route('/buchungsschluessel/export')
@login_required
def buchungsschluessel_export():
    daten = []
    for bs in Buchungsschluessel.query.order_by(Buchungsschluessel.sortierung, Buchungsschluessel.kuerzel).all():
        daten.append({
            'kuerzel': bs.kuerzel,
            'bezeichnung': bs.bezeichnung,
            'buchungstext': bs.buchungstext,
            'soll_klassen': bs.soll_klassen,
            'haben_klassen': bs.haben_klassen,
            'suchbegriffe': bs.suchbegriffe,
            'sortierung': bs.sortierung,
        })
    return Response(json.dumps(daten, indent=2, ensure_ascii=False), mimetype='application/json')


@buchhaltung_bp.route('/buchungsschluessel/import', methods=['GET', 'POST'])
@login_required
def buchungsschluessel_import():
    gem = _gem_context()
    if request.method == 'POST':
        datei = request.files.get('datei')
        if not datei:
            flash('Bitte eine JSON-Datei auswählen.', 'danger')
        else:
            try:
                daten = json.load(datei)
                anzahl = 0
                for eintrag in daten:
                    if Buchungsschluessel.query.filter_by(kuerzel=eintrag.get('kuerzel')).first():
                        continue
                    db.session.add(Buchungsschluessel(
                        kuerzel=eintrag.get('kuerzel'),
                        bezeichnung=eintrag.get('bezeichnung'),
                        buchungstext=eintrag.get('buchungstext'),
                        soll_klassen=eintrag.get('soll_klassen'),
                        haben_klassen=eintrag.get('haben_klassen'),
                        suchbegriffe=eintrag.get('suchbegriffe'),
                        sortierung=eintrag.get('sortierung') or 0,
                        aktiv=True,
                    ))
                    anzahl += 1
                db.session.commit()
                flash(f'{anzahl} Buchungsschlüssel importiert.', 'success')
                return redirect(url_for('buchhaltung.buchungsschluessel_liste'))
            except Exception as exc:
                db.session.rollback()
                flash(str(exc), 'danger')
    return render_template('buchhaltung/buchungsschluessel_import.html', gem=gem)


@buchhaltung_bp.route('/buchungsschluessel/vorschlag')
@login_required
def buchungsschluessel_vorschlag():
    text = request.args.get('text', '').lower()
    for bs in Buchungsschluessel.query.filter_by(aktiv=True).order_by(Buchungsschluessel.sortierung).all():
        begriffe = [teil.strip().lower() for teil in (bs.suchbegriffe or '').split(',') if teil.strip()]
        if any(begriff in text for begriff in begriffe):
            return {
                'kuerzel': bs.kuerzel,
                'buchungstext': bs.buchungstext,
                'soll_konto_id': bs.soll_konto_id,
                'haben_konto_id': bs.haben_konto_id,
            }
    return {}


@buchhaltung_bp.route('/bank-import')
@login_required
def bank_import():
    gem = _gem_context()
    config = BankImportConfig.query.first()
    bankkonten = Konto.query.filter(Konto.kontenklasse == 3, Konto.aktiv == True).order_by(Konto.kontonummer).all()
    echtes_gj = date.today().year
    aktuelles_gj = _aktives_gj()
    return render_template(
        'buchhaltung/bank_import.html',
        gem=gem,
        config=config,
        bankkonten=bankkonten,
        gemeinschaften=_gemeinschaften(),
        geschaeftsjahr=aktuelles_gj,
        echtes_gj=echtes_gj,
        gj_fixiert=aktuelles_gj != echtes_gj,
        gj_optionen=list(range(echtes_gj - 3, echtes_gj + 2)),
    )


@buchhaltung_bp.route('/bank-import/vorschau', methods=['POST'])
@login_required
def bank_import_vorschau():
    gem = _gem_context()
    config = BankImportConfig.query.first()
    datei = request.files.get('datei')
    if not config or not datei:
        flash('Bitte zuerst Konfiguration speichern und eine Datei auswählen.', 'danger')
        return redirect(url_for('buchhaltung.bank_import'))

    dateiinhalt = datei.read()
    geschaeftsjahr = request.form.get('geschaeftsjahr', type=int) or _aktives_gj()
    vorschau = csv_vorschau(dateiinhalt, config, geschaeftsjahr=geschaeftsjahr)
    datei_b64 = base64.b64encode(dateiinhalt).decode('ascii')
    alle_konten = Konto.query.filter_by(aktiv=True).order_by(Konto.kontonummer).all()
    konten = {k.id: k for k in alle_konten}
    schluessel = Buchungsschluessel.query.filter_by(aktiv=True).order_by(
        Buchungsschluessel.sortierung, Buchungsschluessel.kuerzel
    ).all()
    return render_template(
        'buchhaltung/bank_import_vorschau.html',
        gem=gem,
        vorschau=vorschau,
        datei_name=datei.filename,
        datei_b64=datei_b64,
        bank_konto_id=request.form.get('bank_konto_id', type=int),
        geschaeftsjahr=geschaeftsjahr,
        konten=konten,
        alle_konten=alle_konten,
        schluessel=schluessel,
    )


@buchhaltung_bp.route('/bank-import/ausfuehren', methods=['POST'])
@login_required
def bank_import_ausfuehren():
    config = BankImportConfig.query.first()
    datei_b64 = request.form.get('datei_b64', '')
    if not config or not datei_b64:
        flash('Importdaten fehlen.', 'danger')
        return redirect(url_for('buchhaltung.bank_import'))

    manuelle_gegenkonten = {
        key.removeprefix('gegenkonto_'): value
        for key, value in request.form.items()
        if key.startswith('gegenkonto_') and value
    }
    result = csv_importieren(
        base64.b64decode(datei_b64),
        config,
        request.form.get('bank_konto_id', type=int),
        request.form.get('geschaeftsjahr', type=int) or _aktives_gj(),
        current_user.id,
        manuelle_gegenkonten,
    )
    for meldung in result['fehler']:
        flash(meldung, 'danger')
    flash(f"{result['importiert']} Buchungen importiert, {result['uebersprungen']} übersprungen.", 'success')
    return redirect(url_for('buchhaltung.journal'))


@buchhaltung_bp.route('/bank-import/schluessel-anlegen', methods=['POST'])
@login_required
def bank_import_schluessel_anlegen():
    """AJAX: Neuen Buchungsschlüssel aus dem Import-Vorschau-Dialog anlegen."""
    from flask import jsonify
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Keine Daten'}), 400

    kuerzel = (data.get('kuerzel') or '').strip()
    bezeichnung = (data.get('bezeichnung') or '').strip()
    suchbegriff = (data.get('suchbegriff') or '').strip()
    konto_id = data.get('konto_id')
    betrag_positiv = data.get('betrag_positiv', True)

    if not kuerzel or not suchbegriff or not konto_id:
        return jsonify({'error': 'Kürzel, Suchbegriff und Konto sind Pflichtfelder'}), 400

    existing = Buchungsschluessel.query.filter_by(kuerzel=kuerzel).first()
    if existing:
        return jsonify({'error': f'Kürzel \u201e{kuerzel}\u201c existiert bereits'}), 409

    try:
        konto_id = int(konto_id)
    except (ValueError, TypeError):
        return jsonify({'error': 'Ungültige Konto-ID'}), 400

    bs = Buchungsschluessel(
        kuerzel=kuerzel,
        bezeichnung=bezeichnung or kuerzel,
        suchbegriffe=suchbegriff,
        soll_konto_id=None if betrag_positiv else konto_id,
        haben_konto_id=konto_id if betrag_positiv else None,
        aktiv=True,
        sortierung=100,
    )
    db.session.add(bs)
    db.session.commit()

    return jsonify({
        'success': True,
        'konto_id': konto_id,
        'kuerzel': kuerzel,
        'suchbegriff': suchbegriff,
    })


@buchhaltung_bp.route('/konto/ajax-neu', methods=['POST'])
@login_required
def konto_ajax_neu():
    """AJAX: Schnell ein neues Konto anlegen (aus Buchungsschlüssel-Formular)."""
    from flask import jsonify
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Keine Daten'}), 400

    kontonummer = (data.get('kontonummer') or '').strip()
    bezeichnung = (data.get('bezeichnung') or '').strip()
    kontotyp = (data.get('kontotyp') or '').strip()
    try:
        kontenklasse = int(data.get('kontenklasse', -1))
    except (ValueError, TypeError):
        kontenklasse = -1

    if not kontonummer or not bezeichnung or not kontotyp or kontenklasse < 0:
        return jsonify({'error': 'Kontonummer, Bezeichnung, Typ und Klasse sind Pflichtfelder'}), 400

    if Konto.query.filter_by(kontonummer=kontonummer).first():
        return jsonify({'error': f'Kontonummer {kontonummer} existiert bereits'}), 409

    konto = Konto(
        kontonummer=kontonummer,
        bezeichnung=bezeichnung,
        kontenklasse=kontenklasse,
        kontotyp=kontotyp,
        aktiv=True,
    )
    db.session.add(konto)
    db.session.commit()
    return jsonify({'id': konto.id, 'kontonummer': konto.kontonummer, 'bezeichnung': konto.bezeichnung})


@buchhaltung_bp.route('/buchungsschluessel/import-analyse')
@login_required
def buchungsschluessel_import_analyse():
    """
    AJAX: Analysiert alle Import-Buchungstexte auf häufige Textfragmente
    und schlägt neue Buchungsschlüssel vor (für Texte ohne bestehenden Schlüssel).
    """
    from flask import jsonify
    import re
    from collections import Counter

    # Alle Import-Buchungstexte laden
    texte = [
        r[0] for r in
        db.session.query(Buchung.buchungstext)
        .filter(Buchung.buchungsart == 'import', Buchung.storniert == False)
        .distinct().all()
        if r[0]
    ]

    if not texte:
        return jsonify({'vorschlaege': [], 'info': 'Keine Import-Buchungen vorhanden.'})

    # Bestehende Suchbegriffe sammeln
    bestehende_begriffe = set()
    for bs in Buchungsschluessel.query.filter_by(aktiv=True).all():
        for b in (bs.suchbegriffe or '').split(','):
            b = b.strip().lower()
            if b:
                bestehende_begriffe.add(b)

    # Tokens aus Texten extrahieren (Wörter ≥ 4 Zeichen, Zahlen ignorieren)
    token_counter = Counter()
    text_pro_token = {}  # token → Liste von Beispieltexten
    for text in texte:
        # Tokens: zusammenhängende Buchstabenfolgen ≥ 4 Zeichen
        tokens = re.findall(r'[A-Za-zÄÖÜäöüß]{4,}', text)
        # Auch 2-Wort-Kombinationen als Phrase
        woerter = [t for t in tokens if len(t) >= 4]
        alle = list(woerter)
        for i in range(len(woerter) - 1):
            phrase = woerter[i] + ' ' + woerter[i + 1]
            alle.append(phrase)

        gesehen = set()
        for tok in alle:
            tok_lower = tok.lower()
            if tok_lower not in gesehen:
                gesehen.add(tok_lower)
                token_counter[tok_lower] += 1
                if tok_lower not in text_pro_token:
                    text_pro_token[tok_lower] = []
                if len(text_pro_token[tok_lower]) < 3:
                    text_pro_token[tok_lower].append(text[:80])

    # Mindestens 2x vorkommen, nicht bereits als Suchbegriff erfasst
    MIN_TREFFER = 2
    vorschlaege = []
    for token, count in token_counter.most_common(50):
        if count < MIN_TREFFER:
            break
        # Überspringen wenn bereits durch bestehenden Schlüssel abgedeckt
        bereits_abgedeckt = any(token in b or b in token for b in bestehende_begriffe)
        if bereits_abgedeckt:
            continue
        vorschlaege.append({
            'fragment': token,
            'anzahl': count,
            'beispiele': text_pro_token.get(token, []),
        })
        if len(vorschlaege) >= 20:
            break

    return jsonify({
        'vorschlaege': vorschlaege,
        'gesamt_texte': len(texte),
        'info': f'{len(texte)} Import-Buchungstexte analysiert.',
    })


@buchhaltung_bp.route('/bank-import/config', methods=['GET', 'POST'])
@login_required
def bank_import_config():
    gem = _gem_context()
    config = BankImportConfig.query.first()
    if not config:
        config = BankImportConfig()
        db.session.add(config)
        db.session.commit()

    if request.method == 'POST':
        config.bank_name = request.form.get('bank_name', '').strip() or None
        config.spalte_datum = request.form.get('spalte_datum', type=int) or 0
        config.spalte_valuta = request.form.get('spalte_valuta', type=int)
        config.spalte_betrag = request.form.get('spalte_betrag', type=int) or 1
        config.spalte_text = request.form.get('spalte_text', type=int) or 2
        config.spalte_referenz = request.form.get('spalte_referenz', type=int)
        config.trennzeichen = request.form.get('trennzeichen', ';')
        config.datumsformat = request.form.get('datumsformat', '%d.%m.%Y')
        config.dezimaltrennzeichen = request.form.get('dezimaltrennzeichen', ',')
        config.kopfzeilen_ueberspringen = request.form.get('kopfzeilen_ueberspringen', type=int) or 0
        config.encoding = request.form.get('encoding', 'utf-8-sig')
        config.vorzeichen_umkehren = 'vorzeichen_umkehren' in request.form
        db.session.commit()
        flash('Bank-Import-Konfiguration gespeichert.', 'success')
        return redirect(url_for('buchhaltung.bank_import'))

    return render_template('buchhaltung/bank_import_config.html', gem=gem, config=config)
