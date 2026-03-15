"""
Milchvieh-Modul – Blueprint (Phase 1 + 2 + 3).

Bestandsregister, Tierbewegungen, TAMG-Arzneimitteldokumentation,
Impfungen, Laktationserfassung, Reproduktion, MLP, Eutergesundheit,
Klauenpflege, Weidebuch, Tankmilch, KPI-Dashboard und Browser-KI-APIs.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth_decorators import requires_permission
from app.models.milchvieh import (
    Rind, Tierbewegung, Laktation, RindArzneimittelAnwendung, RindImpfung,
    Besamung, MLPPruefung, EuterGesundheit, KlauenpflegeBefund,
    WeidePeriode, TankmilchAuswertung,
    RASSEN_MILCH, TIERBEWEGUNG_TYPEN, VERABREICHUNGSARTEN_RIND,
    IMPF_KRANKHEITEN_RIND, ABGANGSURSACHEN, RIND_STATUS, LAKTATION_STATUS,
    BESAMUNG_ART, SCHALMTEST_ERGEBNISSE, MASTITIS_TYPEN, MASTITIS_ERREGER,
    EUTERVIERTEL, KLAUEN_BEFUNDE, LAMENESS_GRAD,
)
from datetime import datetime, date, timedelta

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

# ── Reproduktion – Besamung ───────────────────────────────────────

@milchvieh_bp.route('/rind/<int:rind_id>/besamung/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def besamung_neu(rind_id):
    rind = Rind.query.get_or_404(rind_id)
    laktation = rind.laktationen.filter_by(ist_aktiv=True).first()
    if request.method == 'POST':
        bs = Besamung(
            rind_id=rind.id,
            laktation_id=laktation.id if laktation else None,
            datum=_parse_date(request.form.get('datum')) or date.today(),
            art=request.form.get('art', 'Künstliche Besamung (KB)'),
            stier_name=request.form.get('stier_name', '').strip() or None,
            stier_hb_nr=request.form.get('stier_hb_nr', '').strip() or None,
            portion_nr=request.form.get('portion_nr', '').strip() or None,
            besamungstechniker=request.form.get('besamungstechniker', '').strip() or None,
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        bs.berechne_kalbetermin(rind.rasse)
        db.session.add(bs)
        db.session.commit()
        flash('Besamung eingetragen.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))
    return render_template('milchvieh/besamung_form.html',
                           rind=rind, besamung=None,
                           besamung_arten=BESAMUNG_ART,
                           laktation=laktation)


@milchvieh_bp.route('/besamung/<int:bs_id>/td', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'edit')
def besamung_td(bs_id):
    bs = Besamung.query.get_or_404(bs_id)
    rind = bs.rind
    if request.method == 'POST':
        bs.td_datum = _parse_date(request.form.get('td_datum')) or date.today()
        bs.traechtig = request.form.get('traechtig') == '1'
        bs.td_methode = request.form.get('td_methode', '').strip() or None
        bs.tierarzt_td = request.form.get('tierarzt_td', '').strip() or None
        db.session.commit()
        flash('Trächtigkeitsdiagnose gespeichert.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))
    return render_template('milchvieh/besamung_td.html', bs=bs, rind=rind)


# ── MLP – Milchleistungsprüfung ───────────────────────────────────

@milchvieh_bp.route('/rind/<int:rind_id>/mlp/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def mlp_neu(rind_id):
    rind = Rind.query.get_or_404(rind_id)
    laktation = rind.laktationen.filter_by(ist_aktiv=True).first()
    if request.method == 'POST':
        pruefung = MLPPruefung(
            rind_id=rind.id,
            laktation_id=laktation.id if laktation else None,
            datum=_parse_date(request.form.get('datum')) or date.today(),
            milchmenge_kg=_parse_float(request.form.get('milchmenge_kg')),
            fett_prozent=_parse_float(request.form.get('fett_prozent')),
            eiweiss_prozent=_parse_float(request.form.get('eiweiss_prozent')),
            laktose_prozent=_parse_float(request.form.get('laktose_prozent')),
            harnstoff_mg_dl=_parse_int(request.form.get('harnstoff_mg_dl')),
            zellzahl_tsd=_parse_int(request.form.get('zellzahl_tsd')),
            pruefer=request.form.get('pruefer', '').strip() or None,
            probenahme_morgen_kg=_parse_float(request.form.get('probenahme_morgen_kg')),
            probenahme_abend_kg=_parse_float(request.form.get('probenahme_abend_kg')),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        if laktation and laktation.kalbedatum and pruefung.datum:
            pruefung.laktationstag = (pruefung.datum - laktation.kalbedatum).days
        pruefung.berechne_kennzahlen()
        db.session.add(pruefung)
        db.session.commit()
        flash('MLP-Prüfung eingetragen.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))
    return render_template('milchvieh/mlp_form.html',
                           rind=rind, pruefung=None, laktation=laktation)


@milchvieh_bp.route('/mlp-auswertung')
@login_required
@requires_permission('milchvieh', 'view')
def mlp_auswertung():
    heute = date.today()
    sub = db.session.query(
        MLPPruefung.rind_id,
        db.func.max(MLPPruefung.datum).label('max_datum')
    ).group_by(MLPPruefung.rind_id).subquery()
    letzte_pruefungen = db.session.query(MLPPruefung).join(
        sub, db.and_(
            MLPPruefung.rind_id == sub.c.rind_id,
            MLPPruefung.datum == sub.c.max_datum
        )
    ).join(Rind).filter(Rind.status == 'aktiv').all()
    return render_template('milchvieh/mlp_auswertung.html',
                           pruefungen=letzte_pruefungen,
                           heute=heute)


# ── Eutergesundheit ───────────────────────────────────────────────

@milchvieh_bp.route('/rind/<int:rind_id>/euter/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def euter_neu(rind_id):
    rind = Rind.query.get_or_404(rind_id)
    if request.method == 'POST':
        befund = EuterGesundheit(
            rind_id=rind.id,
            datum=_parse_date(request.form.get('datum')) or date.today(),
            euterviertel=request.form.get('euterviertel', '').strip() or None,
            schalmtest=request.form.get('schalmtest', '').strip() or None,
            zellzahl_tsd=_parse_int(request.form.get('zellzahl_tsd')),
            erreger=request.form.get('erreger', '').strip() or None,
            mastitis_typ=request.form.get('mastitis_typ', '').strip() or None,
            tierarzt=request.form.get('tierarzt', '').strip() or None,
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(befund)
        db.session.commit()
        flash('Euterbefund eingetragen.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))
    return render_template('milchvieh/euter_form.html',
                           rind=rind,
                           schalmtest_ergebnisse=SCHALMTEST_ERGEBNISSE,
                           mastitis_typen=MASTITIS_TYPEN,
                           mastitis_erreger=MASTITIS_ERREGER,
                           euterviertel=EUTERVIERTEL)


# ── Klauenpflege ──────────────────────────────────────────────────

@milchvieh_bp.route('/rind/<int:rind_id>/klauen/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def klauen_neu(rind_id):
    rind = Rind.query.get_or_404(rind_id)
    if request.method == 'POST':
        befund = KlauenpflegeBefund(
            rind_id=rind.id,
            datum=_parse_date(request.form.get('datum')) or date.today(),
            klauenpfleger=request.form.get('klauenpfleger', '').strip() or None,
            befund=request.form.get('befund', '').strip() or None,
            schweregrad=_parse_int(request.form.get('schweregrad')),
            behandelt=request.form.get('behandelt') == '1',
            naechste_pflege=_parse_date(request.form.get('naechste_pflege')),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(befund)
        db.session.commit()
        flash('Klauenbefund eingetragen.', 'success')
        return redirect(url_for('milchvieh.rind_detail', rind_id=rind.id))
    return render_template('milchvieh/klauen_form.html',
                           rind=rind,
                           klauen_befunde=KLAUEN_BEFUNDE,
                           lameness_grad=LAMENESS_GRAD)


# ── Weidebuch ─────────────────────────────────────────────────────

@milchvieh_bp.route('/weidebuch')
@login_required
@requires_permission('milchvieh', 'view')
def weidebuch():
    jahr = request.args.get('jahr', date.today().year, type=int)
    perioden = WeidePeriode.query.filter(
        db.extract('year', WeidePeriode.datum_von) == jahr
    ).order_by(WeidePeriode.datum_von.desc()).all()
    gesamt_tage = sum(p.weidetage or 0 for p in perioden)
    jahre_raw = db.session.query(
        db.extract('year', WeidePeriode.datum_von).label('j')
    ).distinct().order_by(db.text('j desc')).all()
    verfuegbare_jahre = [int(r.j) for r in jahre_raw] or [date.today().year]
    return render_template('milchvieh/weidebuch.html',
                           perioden=perioden,
                           gesamt_tage=gesamt_tage,
                           oepul_ziel=120,
                           jahr=jahr,
                           verfuegbare_jahre=verfuegbare_jahre)


@milchvieh_bp.route('/weidebuch/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def weide_neu():
    if request.method == 'POST':
        periode = WeidePeriode(
            datum_von=_parse_date(request.form.get('datum_von')) or date.today(),
            datum_bis=_parse_date(request.form.get('datum_bis')),
            weide_bezeichnung=request.form.get('weide_bezeichnung', '').strip() or None,
            weide_flaeche_ha=_parse_float(request.form.get('weide_flaeche_ha')),
            anzahl_tiere=_parse_int(request.form.get('anzahl_tiere')),
            tier_gruppe=request.form.get('tier_gruppe', '').strip() or None,
            stunden_pro_tag=_parse_float(request.form.get('stunden_pro_tag')),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(periode)
        db.session.commit()
        flash('Weideperiode eingetragen.', 'success')
        return redirect(url_for('milchvieh.weidebuch'))
    return render_template('milchvieh/weide_form.html', periode=None)


@milchvieh_bp.route('/weidebuch/<int:periode_id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'edit')
def weide_edit(periode_id):
    periode = WeidePeriode.query.get_or_404(periode_id)
    if request.method == 'POST':
        periode.datum_von = _parse_date(request.form.get('datum_von')) or periode.datum_von
        periode.datum_bis = _parse_date(request.form.get('datum_bis'))
        periode.weide_bezeichnung = request.form.get('weide_bezeichnung', '').strip() or None
        periode.weide_flaeche_ha = _parse_float(request.form.get('weide_flaeche_ha'))
        periode.anzahl_tiere = _parse_int(request.form.get('anzahl_tiere'))
        periode.tier_gruppe = request.form.get('tier_gruppe', '').strip() or None
        periode.stunden_pro_tag = _parse_float(request.form.get('stunden_pro_tag'))
        periode.bemerkung = request.form.get('bemerkung', '').strip() or None
        db.session.commit()
        flash('Weideperiode gespeichert.', 'success')
        return redirect(url_for('milchvieh.weidebuch'))
    return render_template('milchvieh/weide_form.html', periode=periode)


# ── Tankmilch ─────────────────────────────────────────────────────

@milchvieh_bp.route('/tankmilch')
@login_required
@requires_permission('milchvieh', 'view')
def tankmilch():
    auswertungen = TankmilchAuswertung.query.order_by(
        TankmilchAuswertung.jahr.desc(),
        TankmilchAuswertung.monat.desc()
    ).limit(24).all()
    return render_template('milchvieh/tankmilch.html', auswertungen=auswertungen)


@milchvieh_bp.route('/tankmilch/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('milchvieh', 'create')
def tankmilch_neu():
    if request.method == 'POST':
        auswertung = TankmilchAuswertung(
            jahr=_parse_int(request.form.get('jahr'), date.today().year),
            monat=_parse_int(request.form.get('monat'), date.today().month),
            milchmenge_kg=_parse_float(request.form.get('milchmenge_kg')),
            fett_prozent=_parse_float(request.form.get('fett_prozent')),
            eiweiss_prozent=_parse_float(request.form.get('eiweiss_prozent')),
            gesamtkeimzahl=_parse_int(request.form.get('gesamtkeimzahl')),
            zellzahl_tank=_parse_int(request.form.get('zellzahl_tank')),
            gefrierpunkt=_parse_float(request.form.get('gefrierpunkt')),
            hemmstoff=request.form.get('hemmstoff') == '1',
            auszahlungspreis_ct_kg=_parse_float(request.form.get('auszahlungspreis_ct_kg')),
            qualitaetszuschlag_ct=_parse_float(request.form.get('qualitaetszuschlag_ct')),
            molkerei=request.form.get('molkerei', '').strip() or None,
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(auswertung)
        db.session.commit()
        flash('Tankmilch-Auswertung gespeichert.', 'success')
        return redirect(url_for('milchvieh.tankmilch'))
    return render_template('milchvieh/tankmilch_form.html', auswertung=None)


# ── KPI-Dashboard ─────────────────────────────────────────────────

@milchvieh_bp.route('/dashboard')
@login_required
@requires_permission('milchvieh', 'view')
def dashboard():
    heute = date.today()
    rinder_aktiv = Rind.query.filter_by(status='aktiv').all()
    n = len(rinder_aktiv)
    kuehe = [r for r in rinder_aktiv if r.geschlecht == 'W' and
             r.alter_monate and r.alter_monate >= 24]

    lakt_zahlen = []
    for r in kuehe:
        lakt = r.laktationen.filter_by(ist_aktiv=True).first()
        if lakt and lakt.laktationsnummer:
            lakt_zahlen.append(lakt.laktationsnummer)
    avg_lakt = round(sum(lakt_zahlen) / len(lakt_zahlen), 1) if lakt_zahlen else None

    wartezeit_milch = RindArzneimittelAnwendung.query.filter(
        RindArzneimittelAnwendung.wartezeit_milch_ende >= heute
    ).count()
    wartezeit_fleisch = RindArzneimittelAnwendung.query.filter(
        RindArzneimittelAnwendung.wartezeit_fleisch_ende >= heute
    ).count()

    sub = db.session.query(
        MLPPruefung.rind_id,
        db.func.max(MLPPruefung.datum).label('md')
    ).group_by(MLPPruefung.rind_id).subquery()
    letzte_mlp = db.session.query(MLPPruefung).join(
        sub, db.and_(MLPPruefung.rind_id == sub.c.rind_id, MLPPruefung.datum == sub.c.md)
    ).join(Rind).filter(Rind.status == 'aktiv').all()

    scc_erhoet = sum(1 for p in letzte_mlp if p.zellzahl_tsd and p.zellzahl_tsd >= 200)
    scc_kritisch = sum(1 for p in letzte_mlp if p.zellzahl_tsd and p.zellzahl_tsd >= 400)
    anteil_scc_ok = round((len(letzte_mlp) - scc_erhoet) / len(letzte_mlp) * 100) if letzte_mlp else None

    zkz_werte = []
    guestzeit_werte = []
    for r in kuehe:
        lakt = r.laktationen.filter_by(ist_aktiv=True).first()
        if lakt:
            if lakt.zwischenkalbezeit_tage:
                zkz_werte.append(lakt.zwischenkalbezeit_tage)
            if lakt.guestzeit_tage:
                guestzeit_werte.append(lakt.guestzeit_tage)
    avg_zkz = round(sum(zkz_werte) / len(zkz_werte)) if zkz_werte else None
    avg_guestzeit = round(sum(guestzeit_werte) / len(guestzeit_werte)) if guestzeit_werte else None

    letzte_tankmilch = TankmilchAuswertung.query.order_by(
        TankmilchAuswertung.jahr.desc(), TankmilchAuswertung.monat.desc()
    ).limit(3).all()

    ama_faellig = sum(1 for r in rinder_aktiv if r.ama_meldung_faellig)

    weidetage_jahr = sum(
        (p.weidetage or 0) for p in WeidePeriode.query.filter(
            db.extract('year', WeidePeriode.datum_von) == heute.year
        ).all()
    )

    # Aufgaben-Widget (Phase 3): fällige Kalbetermine + Trockenstell-Empfehlungen
    aufgaben = []
    for r in rinder_aktiv:
        if r.geschlecht != 'W':
            continue
        lakt = r.laktationen.filter_by(ist_aktiv=True).first()
        if not lakt:
            continue
        # Trächtige Besamung → Kalbetermin
        tragende = lakt.tragende_besamung
        if tragende:
            kt = tragende.berechne_kalbetermin(r.rasse)
            if kt:
                tage_bis = (kt - heute).days
                if -7 <= tage_bis <= 60:
                    aufgaben.append({
                        'typ': 'kalbetermin',
                        'rind_id': r.id,
                        'ohrmarke': r.ohrmarke,
                        'name': r.name,
                        'datum': kt.strftime('%d.%m.%Y'),
                        'tage': tage_bis,
                        'icon': 'bi-calendar-event',
                        'klasse': 'danger' if tage_bis <= 7 else ('warning' if tage_bis <= 21 else 'info'),
                    })
        # Trockenstell-Empfehlung: 60 Tage vor erwartetem Kalbetermin
        if tragende:
            kt = tragende.berechne_kalbetermin(r.rasse)
            if kt:
                ts_datum = kt - timedelta(days=60)
                tage_bis_ts = (ts_datum - heute).days
                if 0 <= tage_bis_ts <= 14:
                    aufgaben.append({
                        'typ': 'trockenstellen',
                        'rind_id': r.id,
                        'ohrmarke': r.ohrmarke,
                        'name': r.name,
                        'datum': ts_datum.strftime('%d.%m.%Y'),
                        'tage': tage_bis_ts,
                        'icon': 'bi-moon-stars',
                        'klasse': 'warning',
                    })
    aufgaben.sort(key=lambda x: x['tage'])

    return render_template('milchvieh/dashboard.html',
                           heute=heute,
                           n_aktiv=n,
                           n_kuehe=len(kuehe),
                           avg_lakt=avg_lakt,
                           wartezeit_milch=wartezeit_milch,
                           wartezeit_fleisch=wartezeit_fleisch,
                           scc_erhoet=scc_erhoet,
                           scc_kritisch=scc_kritisch,
                           anteil_scc_ok=anteil_scc_ok,
                           n_mlp=len(letzte_mlp),
                           avg_zkz=avg_zkz,
                           avg_guestzeit=avg_guestzeit,
                           letzte_tankmilch=letzte_tankmilch,
                           ama_faellig=ama_faellig,
                           weidetage_jahr=weidetage_jahr,
                           aufgaben=aufgaben)


# ── Phase 3: Browser-KI-APIs ──────────────────────────────────────


@milchvieh_bp.route('/api/tiere')
@login_required
@requires_permission('milchvieh', 'view')
def api_tiere():
    """JSON-Index aller aktiven Rinder für clientseitiges Autocomplete."""
    rinder = Rind.query.filter_by(status='aktiv').order_by(Rind.ohrmarke).all()
    return jsonify([{
        'id': r.id,
        'ohrmarke': r.ohrmarke,
        'name': r.name or '',
        'rasse': r.rasse or '',
        'geschlecht': r.geschlecht,
        'alter_monate': r.alter_monate,
    } for r in rinder])


@milchvieh_bp.route('/api/arzneimittel_history')
@login_required
@requires_permission('milchvieh', 'view')
def api_arzneimittel_history():
    """Distinct Arzneimittel aus der eigenen TAMG-Geschichte für Autocomplete + AI-Kontext."""
    rows = db.session.query(
        RindArzneimittelAnwendung.arzneimittel_name,
        RindArzneimittelAnwendung.wirkstoff,
        RindArzneimittelAnwendung.wartezeit_milch_tage,
        RindArzneimittelAnwendung.wartezeit_fleisch_tage,
        RindArzneimittelAnwendung.ist_antibiotikum,
        RindArzneimittelAnwendung.verabreichungsart,
        RindArzneimittelAnwendung.diagnose,
    ).filter(
        RindArzneimittelAnwendung.arzneimittel_name.isnot(None)
    ).order_by(
        RindArzneimittelAnwendung.beginn.desc()
    ).limit(500).all()

    # Deduplizieren nach Name (letzter Eintrag gewinnt)
    seen = {}
    for row in rows:
        n = row.arzneimittel_name.strip()
        if n not in seen:
            seen[n] = {
                'name': n,
                'wirkstoff': row.wirkstoff or '',
                'wz_milch': row.wartezeit_milch_tage or 0,
                'wz_fleisch': row.wartezeit_fleisch_tage or 0,
                'antibiotikum': bool(row.ist_antibiotikum),
                'verabreichungsart': row.verabreichungsart or '',
                'diagnose': row.diagnose or '',
            }
    return jsonify(list(seen.values()))


@milchvieh_bp.route('/api/gve')
@login_required
@requires_permission('milchvieh', 'view')
def api_gve():
    """GVE-Berechnung (INVEKOS AT) für alle aktiven Tiere."""
    heute = date.today()
    rinder = Rind.query.filter_by(status='aktiv').all()

    # GVE-Koeffizienten AT (INVEKOS)
    def gve_koeff(r):
        if not r.geburtsdatum:
            return 0.6
        alter_m = r.alter_monate or 0
        if r.geschlecht == 'W' and alter_m >= 24:
            lakt = r.laktationen.filter_by(ist_aktiv=True).first()
            if lakt:
                return 1.0  # Milchkuh
            return 0.6
        if alter_m < 6:
            return 0.4
        if alter_m < 24:
            return 0.6
        return 0.6

    gve_total = sum(gve_koeff(r) for r in rinder)
    return jsonify({
        'n_tiere': len(rinder),
        'gve_total': round(gve_total, 2),
        'tiere': [{
            'ohrmarke': r.ohrmarke,
            'name': r.name or '',
            'koeff': gve_koeff(r),
        } for r in rinder],
    })
