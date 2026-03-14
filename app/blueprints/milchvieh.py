"""
Milchvieh-Modul – Blueprint (Phase 1).

Bestandsregister, Tierbewegungen, TAMG-Arzneimitteldokumentation,
Impfungen und Laktationserfassung.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.extensions import db
from app.auth_decorators import requires_permission
from app.models.milchvieh import (
    Rind, Tierbewegung, Laktation, RindArzneimittelAnwendung, RindImpfung,
    RASSEN_MILCH, TIERBEWEGUNG_TYPEN, VERABREICHUNGSARTEN_RIND,
    IMPF_KRANKHEITEN_RIND, ABGANGSURSACHEN, RIND_STATUS, LAKTATION_STATUS,
)
from datetime import datetime, date

milchvieh_bp = Blueprint('milchvieh', __name__, url_prefix='/milchvieh')


# ── Hilfsfunktionen ──────────────────────────────────────────────

def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val.strip(), '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


def _parse_int(val, default=None):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _parse_float(val, default=None):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ── Bestandsübersicht ────────────────────────────────────────────

@milchvieh_bp.route('/')
@login_required
@requires_permission('milchvieh', 'view')
def index():
    """Bestandsübersicht mit KPIs."""
    heute = date.today()

    rinder_aktiv = Rind.query.filter_by(status='aktiv').order_by(Rind.ohrmarke).all()
    rinder_gesamt = len(rinder_aktiv)

    # Kühe mit aktiver Wartezeit (Milch)
    wartezeit_milch = RindArzneimittelAnwendung.query.filter(
        RindArzneimittelAnwendung.wartezeit_milch_ende >= heute
    ).count()

    # AMA-Meldungen fällig
    ama_faellig = sum(1 for r in rinder_aktiv if r.ama_meldung_faellig)

    # Bald fällige Impfungen (14 Tage)
    naechste_impfungen = RindImpfung.query.filter(
        RindImpfung.naechste_impfung <= date.fromordinal(heute.toordinal() + 14),
        RindImpfung.naechste_impfung >= heute,
    ).count()

    return render_template('milchvieh/index.html',
                           rinder_aktiv=rinder_aktiv,
                           rinder_gesamt=rinder_gesamt,
                           wartezeit_milch=wartezeit_milch,
                           ama_faellig=ama_faellig,
                           naechste_impfungen=naechste_impfungen)


# ── Bestandsregister (Rinder) ────────────────────────────────────

@milchvieh_bp.route('/bestand')
@login_required
@requires_permission('milchvieh', 'view')
def bestand():
    """Vollständiges Bestandsregister."""
    status_filter = request.args.get('status', 'aktiv')
    query = Rind.query
    if status_filter != 'alle':
        query = query.filter_by(status=status_filter)
    rinder = query.order_by(Rind.ohrmarke).all()
    return render_template('milchvieh/bestand.html',
                           rinder=rinder,
                           status_filter=status_filter,
                           rind_status=RIND_STATUS)


@milchvieh_bp.route('/rind/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def rind_neu():
    """Neues Rind anlegen (Zugang oder Geburt)."""
    if request.method == 'POST':
        rind = Rind(
            ohrmarke=request.form.get('ohrmarke', '').strip().upper(),
            ohrmarke_2=request.form.get('ohrmarke_2', '').strip().upper() or None,
            name=request.form.get('name', '').strip() or None,
            rasse=request.form.get('rasse', '').strip() or None,
            geschlecht=request.form.get('geschlecht', 'W'),
            geburtsdatum=_parse_date(request.form.get('geburtsdatum')),
            geburtsgewicht_kg=_parse_float(request.form.get('geburtsgewicht_kg')),
            mutter_ohrmarke=request.form.get('mutter_ohrmarke', '').strip().upper() or None,
            vater_hb_nr=request.form.get('vater_hb_nr', '').strip() or None,
            herkunft_betrieb=request.form.get('herkunft_betrieb', '').strip() or None,
            herkunft_land=request.form.get('herkunft_land', '').strip() or None,
            eingang_datum=_parse_date(request.form.get('eingang_datum')),
            nutzungsart=request.form.get('nutzungsart', 'Milch'),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(rind)
        db.session.flush()  # ID generieren

        # Tierbewegung anlegen
        bewegung_typ = request.form.get('bewegung_typ', 'zukauf')
        bewegung = Tierbewegung(
            rind_id=rind.id,
            datum=rind.eingang_datum or rind.geburtsdatum or date.today(),
            typ=bewegung_typ,
            gegenpartei_betrieb=rind.herkunft_betrieb,
            gegenpartei_land=rind.herkunft_land,
            gewicht_kg=rind.geburtsgewicht_kg,
        )
        db.session.add(bewegung)
        db.session.commit()
        flash(f'Rind {rind.ohrmarke} angelegt.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))

    return render_template('milchvieh/rind_form.html',
                           rind=None,
                           rassen=RASSEN_MILCH,
                           bewegung_typen=TIERBEWEGUNG_TYPEN)


@milchvieh_bp.route('/rind/<int:rind_id>')
@login_required
@requires_permission('milchvieh', 'view')
def rind_detail(rind_id):
    """Detailansicht eines Rindes."""
    rind = Rind.query.get_or_404(rind_id)
    bewegungen = rind.tierbewegungen.order_by(Tierbewegung.datum.desc()).all()
    arzneimittel = rind.arzneimittel_anwendungen.order_by(
        RindArzneimittelAnwendung.beginn.desc()).all()
    impfungen = rind.impfungen.order_by(RindImpfung.datum.desc()).all()
    laktationen = rind.laktationen.order_by(Laktation.laktationsnummer.desc()).all()
    return render_template('milchvieh/rind_detail.html',
                           rind=rind,
                           bewegungen=bewegungen,
                           arzneimittel=arzneimittel,
                           impfungen=impfungen,
                           laktationen=laktationen,
                           today=date.today())


@milchvieh_bp.route('/rind/<int:rind_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'edit')
def rind_edit(rind_id):
    """Rind bearbeiten."""
    rind = Rind.query.get_or_404(rind_id)
    if request.method == 'POST':
        rind.name = request.form.get('name', '').strip() or None
        rind.rasse = request.form.get('rasse', '').strip() or None
        rind.geschlecht = request.form.get('geschlecht', 'W')
        rind.geburtsdatum = _parse_date(request.form.get('geburtsdatum'))
        rind.geburtsgewicht_kg = _parse_float(request.form.get('geburtsgewicht_kg'))
        rind.mutter_ohrmarke = request.form.get('mutter_ohrmarke', '').strip().upper() or None
        rind.vater_hb_nr = request.form.get('vater_hb_nr', '').strip() or None
        rind.herkunft_betrieb = request.form.get('herkunft_betrieb', '').strip() or None
        rind.herkunft_land = request.form.get('herkunft_land', '').strip() or None
        rind.eingang_datum = _parse_date(request.form.get('eingang_datum'))
        rind.nutzungsart = request.form.get('nutzungsart', 'Milch')
        rind.ama_gemeldet = request.form.get('ama_gemeldet') == '1'
        rind.ama_meldedatum = _parse_date(request.form.get('ama_meldedatum'))
        rind.bemerkung = request.form.get('bemerkung', '').strip() or None
        db.session.commit()
        flash('Rind gespeichert.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))

    return render_template('milchvieh/rind_form.html',
                           rind=rind,
                           rassen=RASSEN_MILCH,
                           bewegung_typen=TIERBEWEGUNG_TYPEN)


@milchvieh_bp.route('/rind/<int:rind_id>/abgang', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'edit')
def rind_abgang(rind_id):
    """Abgang eines Rindes erfassen."""
    rind = Rind.query.get_or_404(rind_id)
    if request.method == 'POST':
        typ = request.form.get('typ', 'abgang_verkauf')
        abgang_datum = _parse_date(request.form.get('datum')) or date.today()

        rind.status = 'geschlachtet' if 'schlachtung' in typ else (
            'verendet' if 'verendung' in typ else 'abgegangen')
        rind.abgang_datum = abgang_datum
        rind.abgangsursache = request.form.get('abgangsursache', '').strip() or None

        bewegung = Tierbewegung(
            rind_id=rind.id,
            datum=abgang_datum,
            typ=typ,
            gegenpartei_betrieb=request.form.get('gegenpartei_betrieb', '').strip() or None,
            schlachthof=request.form.get('schlachthof', '').strip() or None,
            gewicht_kg=_parse_float(request.form.get('gewicht_kg')),
            preis=_parse_float(request.form.get('preis')),
            beleg_nr=request.form.get('beleg_nr', '').strip() or None,
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(bewegung)
        db.session.commit()
        flash(f'Abgang für Rind {rind.ohrmarke} erfasst.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))

    return render_template('milchvieh/rind_abgang.html',
                           rind=rind,
                           abgangsursachen=ABGANGSURSACHEN,
                           bewegung_typen=TIERBEWEGUNG_TYPEN)


# ── TAMG – Arzneimittel ──────────────────────────────────────────

@milchvieh_bp.route('/rind/<int:rind_id>/arzneimittel/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def arzneimittel_neu(rind_id):
    """Neue Arzneimittel-Anwendung erfassen."""
    rind = Rind.query.get_or_404(rind_id)
    if request.method == 'POST':
        anwendung = RindArzneimittelAnwendung(
            rind_id=rind.id,
            beginn=_parse_date(request.form.get('beginn')) or date.today(),
            ende=_parse_date(request.form.get('ende')),
            arzneimittel_name=request.form.get('arzneimittel_name', '').strip(),
            wirkstoff=request.form.get('wirkstoff', '').strip() or None,
            zulassungsnummer=request.form.get('zulassungsnummer', '').strip() or None,
            charge=request.form.get('charge', '').strip() or None,
            dosierung=request.form.get('dosierung', '').strip() or None,
            verabreichungsart=request.form.get('verabreichungsart', '').strip() or None,
            behandlungsdauer_tage=_parse_int(request.form.get('behandlungsdauer_tage')),
            anzahl_tiere=_parse_int(request.form.get('anzahl_tiere'), 1),
            diagnose=request.form.get('diagnose', '').strip() or None,
            tierarzt_name=request.form.get('tierarzt_name', '').strip() or None,
            rezept_nr=request.form.get('rezept_nr', '').strip() or None,
            ist_antibiotikum=request.form.get('ist_antibiotikum') == '1',
            wartezeit_milch_tage=_parse_int(request.form.get('wartezeit_milch_tage'), 0),
            wartezeit_fleisch_tage=_parse_int(request.form.get('wartezeit_fleisch_tage'), 0),
            beleg_nr=request.form.get('beleg_nr', '').strip() or None,
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        anwendung.berechne_wartezeiten()
        db.session.add(anwendung)
        db.session.commit()
        flash('Arzneimittel-Anwendung eingetragen.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))

    return render_template('milchvieh/arzneimittel_form.html',
                           rind=rind,
                           anwendung=None,
                           verabreichungsarten=VERABREICHUNGSARTEN_RIND)


@milchvieh_bp.route('/arzneimittel/<int:anwendung_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'edit')
def arzneimittel_edit(anwendung_id):
    """Arzneimittel-Anwendung bearbeiten."""
    anwendung = RindArzneimittelAnwendung.query.get_or_404(anwendung_id)
    rind = anwendung.rind
    if request.method == 'POST':
        anwendung.beginn = _parse_date(request.form.get('beginn')) or anwendung.beginn
        anwendung.ende = _parse_date(request.form.get('ende'))
        anwendung.arzneimittel_name = request.form.get('arzneimittel_name', '').strip()
        anwendung.wirkstoff = request.form.get('wirkstoff', '').strip() or None
        anwendung.zulassungsnummer = request.form.get('zulassungsnummer', '').strip() or None
        anwendung.charge = request.form.get('charge', '').strip() or None
        anwendung.dosierung = request.form.get('dosierung', '').strip() or None
        anwendung.verabreichungsart = request.form.get('verabreichungsart', '').strip() or None
        anwendung.behandlungsdauer_tage = _parse_int(request.form.get('behandlungsdauer_tage'))
        anwendung.anzahl_tiere = _parse_int(request.form.get('anzahl_tiere'), 1)
        anwendung.diagnose = request.form.get('diagnose', '').strip() or None
        anwendung.tierarzt_name = request.form.get('tierarzt_name', '').strip() or None
        anwendung.rezept_nr = request.form.get('rezept_nr', '').strip() or None
        anwendung.ist_antibiotikum = request.form.get('ist_antibiotikum') == '1'
        anwendung.wartezeit_milch_tage = _parse_int(request.form.get('wartezeit_milch_tage'), 0)
        anwendung.wartezeit_fleisch_tage = _parse_int(request.form.get('wartezeit_fleisch_tage'), 0)
        anwendung.beleg_nr = request.form.get('beleg_nr', '').strip() or None
        anwendung.bemerkung = request.form.get('bemerkung', '').strip() or None
        anwendung.berechne_wartezeiten()
        db.session.commit()
        flash('Arzneimittel-Anwendung gespeichert.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))

    return render_template('milchvieh/arzneimittel_form.html',
                           rind=rind,
                           anwendung=anwendung,
                           verabreichungsarten=VERABREICHUNGSARTEN_RIND)


# ── Impfungen ────────────────────────────────────────────────────

@milchvieh_bp.route('/rind/<int:rind_id>/impfung/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def impfung_neu(rind_id):
    """Neue Impfung erfassen."""
    rind = Rind.query.get_or_404(rind_id)
    if request.method == 'POST':
        impfung = RindImpfung(
            rind_id=rind.id,
            datum=_parse_date(request.form.get('datum')) or date.today(),
            impfstoff=request.form.get('impfstoff', '').strip() or None,
            krankheit=request.form.get('krankheit', '').strip() or None,
            charge=request.form.get('charge', '').strip() or None,
            verabreichungsart=request.form.get('verabreichungsart', '').strip() or None,
            tierarzt=request.form.get('tierarzt', '').strip() or None,
            naechste_impfung=_parse_date(request.form.get('naechste_impfung')),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(impfung)
        db.session.commit()
        flash('Impfung eingetragen.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))

    return render_template('milchvieh/impfung_form.html',
                           rind=rind,
                           impfung=None,
                           krankheiten=IMPF_KRANKHEITEN_RIND,
                           verabreichungsarten=VERABREICHUNGSARTEN_RIND)


# ── Laktation ────────────────────────────────────────────────────

@milchvieh_bp.route('/rind/<int:rind_id>/laktation/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def laktation_neu(rind_id):
    """Neue Laktation / Kalbung erfassen."""
    rind = Rind.query.get_or_404(rind_id)
    if request.method == 'POST':
        # Alte aktive Laktation beenden
        alte = rind.laktationen.filter_by(ist_aktiv=True).first()
        if alte:
            alte.ist_aktiv = False
            alte.laktations_ende = _parse_date(request.form.get('kalbedatum'))

        laktation = Laktation(
            rind_id=rind.id,
            laktationsnummer=_parse_int(request.form.get('laktationsnummer')),
            kalbedatum=_parse_date(request.form.get('kalbedatum')),
            kalbeverlauf=request.form.get('kalbeverlauf', '').strip() or None,
            kalb_ohrmarke=request.form.get('kalb_ohrmarke', '').strip().upper() or None,
            kalb_geschlecht=request.form.get('kalb_geschlecht', '').strip() or None,
            status='laktierend',
            ist_aktiv=True,
        )
        db.session.add(laktation)
        db.session.commit()
        flash('Laktation / Kalbung erfasst.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))

    # Laktationsnummer vorschlagen
    letzte = rind.laktationen.order_by(Laktation.laktationsnummer.desc()).first()
    naechste_nr = (letzte.laktationsnummer or 0) + 1 if letzte else 1

    return render_template('milchvieh/laktation_form.html',
                           rind=rind,
                           laktation=None,
                           naechste_nr=naechste_nr,
                           laktation_status=LAKTATION_STATUS)


# ── TAMG-Journal (Gesamt) ────────────────────────────────────────

@milchvieh_bp.route('/tamg-journal')
@login_required
@requires_permission('milchvieh', 'view')
def tamg_journal():
    """TAMG-Behandlungsjournal aller Rinder."""
    heute = date.today()
    anwendungen = RindArzneimittelAnwendung.query.join(Rind).filter(
        Rind.status == 'aktiv'
    ).order_by(RindArzneimittelAnwendung.beginn.desc()).all()

    aktive_wartezeiten = [a for a in anwendungen
                          if a.wartezeit_milch_aktiv or a.wartezeit_fleisch_aktiv]

    return render_template('milchvieh/tamg_journal.html',
                           anwendungen=anwendungen,
                           aktive_wartezeiten=aktive_wartezeiten,
                           heute=heute)
