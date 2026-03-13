"""
Legehennen Pro-Modul – Blueprint.

Herdenmanagement, Stallbuch, Sortierergebnisse, Tierarzt,
Impfungen, Medikamente, Salmonellen, Futter, Legekurve.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.auth_decorators import requires_permission
from app.models.legehennen import (
    Herde, Tagesleistung, Sortierergebnis, TierarztBesuch,
    Impfung, MedikamentBehandlung, FutterLieferung,
    SalmonellenProbe, HerdeEreignis,
    HALTUNGSFORMEN, MEDIKAMENT_TYPEN, VERABREICHUNGSARTEN,
    IMPF_KRANKHEITEN, PROBENARTEN, EREIGNIS_KATEGORIEN,
)
from datetime import datetime, date

legehennen_bp = Blueprint('legehennen', __name__, url_prefix='/legehennen')


# ── Hilfsfunktionen ──────────────────────────────────────────────

def _parse_date(val):
    """Datum aus Formular-String parsen."""
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


# ── Herden-Übersicht ─────────────────────────────────────────────

@legehennen_bp.route('/')
@login_required
@requires_permission('legehennen', 'view')
def index():
    """Herden-Übersicht mit KPIs."""
    herden_aktiv = Herde.query.filter_by(ist_aktiv=True).order_by(Herde.name).all()
    herden_archiv = Herde.query.filter_by(ist_aktiv=False).order_by(Herde.ausstalldatum.desc()).all()

    # KPIs berechnen
    gesamtbestand = sum(h.aktueller_bestand or 0 for h in herden_aktiv)
    heute = date.today()
    # Heutige Eier (alle aktiven Herden)
    eier_heute = db.session.query(
        db.func.sum(Tagesleistung.eier_gesamt)
    ).join(Herde).filter(
        Herde.ist_aktiv == True,
        Tagesleistung.datum == heute
    ).scalar() or 0

    # Aktive Wartezeiten
    wartezeiten_aktiv = MedikamentBehandlung.query.filter(
        MedikamentBehandlung.wartezeit_ende >= heute
    ).count()

    return render_template('legehennen/index.html',
                           herden_aktiv=herden_aktiv,
                           herden_archiv=herden_archiv,
                           gesamtbestand=gesamtbestand,
                           eier_heute=eier_heute,
                           wartezeiten_aktiv=wartezeiten_aktiv,
                           haltungsformen=HALTUNGSFORMEN)


# ── Herde CRUD ───────────────────────────────────────────────────

@legehennen_bp.route('/herde/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('legehennen', 'create')
def herde_neu():
    """Neue Herde anlegen."""
    if request.method == 'POST':
        anfangsbestand = _parse_int(request.form.get('anfangsbestand'), 0)
        herde = Herde(
            name=request.form.get('name', '').strip(),
            rasse=request.form.get('rasse', '').strip() or None,
            haltungsform=_parse_int(request.form.get('haltungsform'), 2),
            schlupfdatum=_parse_date(request.form.get('schlupfdatum')),
            lieferdatum=_parse_date(request.form.get('lieferdatum')),
            lieferant=request.form.get('lieferant', '').strip() or None,
            lieferant_vvvo=request.form.get('lieferant_vvvo', '').strip() or None,
            anfangsbestand=anfangsbestand,
            aktueller_bestand=anfangsbestand,
            stall_nr=request.form.get('stall_nr', '').strip() or None,
            stall_flaeche_m2=_parse_float(request.form.get('stall_flaeche_m2')),
            auslauf_flaeche_m2=_parse_float(request.form.get('auslauf_flaeche_m2')),
            nest_plaetze=_parse_int(request.form.get('nest_plaetze')),
            erzeuger_code=request.form.get('erzeuger_code', '').strip() or None,
            legebeginn=_parse_date(request.form.get('legebeginn')),
            erwartetes_ende=_parse_date(request.form.get('erwartetes_ende')),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(herde)
        db.session.commit()
        flash(f'Herde „{herde.name}" erstellt.', 'success')
        return redirect(url_for('legehennen.herde_detail', id=herde.id))

    return render_template('legehennen/herde_form.html',
                           herde=None,
                           haltungsformen=HALTUNGSFORMEN)


@legehennen_bp.route('/herde/<int:id>')
@login_required
@requires_permission('legehennen', 'view')
def herde_detail(id):
    """Herden-Detailseite mit Tabs: Übersicht, Stallbuch, Sortierung, …"""
    herde = Herde.query.get_or_404(id)
    tab = request.args.get('tab', 'uebersicht')

    # Letzte Tagesleistungen
    tagesleistungen = herde.tagesleistungen.order_by(Tagesleistung.datum.desc()).limit(30).all()
    # Letzte Sortierergebnisse
    sortierergebnisse = herde.sortierergebnisse.order_by(Sortierergebnis.datum.desc()).limit(20).all()
    # Tierarzt
    tierarzt_besuche = herde.tierarzt_besuche.order_by(TierarztBesuch.datum.desc()).all()
    # Impfungen
    impfungen = herde.impfungen.order_by(Impfung.datum.desc()).all()
    # Medikamente
    medikamente = herde.medikament_behandlungen.order_by(MedikamentBehandlung.beginn.desc()).all()
    # Salmonellen
    salmonellen = herde.salmonellen_proben.order_by(SalmonellenProbe.probenahme_datum.desc()).all()
    # Futter
    futter = herde.futter_lieferungen.order_by(FutterLieferung.datum.desc()).all()
    # Ereignisse
    ereignisse = herde.ereignisse.order_by(HerdeEreignis.datum.desc()).all()

    return render_template('legehennen/herde_detail.html',
                           herde=herde,
                           tab=tab,
                           tagesleistungen=tagesleistungen,
                           sortierergebnisse=sortierergebnisse,
                           tierarzt_besuche=tierarzt_besuche,
                           impfungen=impfungen,
                           medikamente=medikamente,
                           salmonellen=salmonellen,
                           futter=futter,
                           ereignisse=ereignisse,
                           haltungsformen=HALTUNGSFORMEN,
                           medikament_typen=MEDIKAMENT_TYPEN,
                           verabreichungsarten=VERABREICHUNGSARTEN,
                           impf_krankheiten=IMPF_KRANKHEITEN,
                           probenarten=PROBENARTEN,
                           ereignis_kategorien=EREIGNIS_KATEGORIEN)


@legehennen_bp.route('/herde/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission('legehennen', 'edit')
def herde_edit(id):
    """Herde bearbeiten."""
    herde = Herde.query.get_or_404(id)

    if request.method == 'POST':
        herde.name = request.form.get('name', '').strip()
        herde.rasse = request.form.get('rasse', '').strip() or None
        herde.haltungsform = _parse_int(request.form.get('haltungsform'), 2)
        herde.schlupfdatum = _parse_date(request.form.get('schlupfdatum'))
        herde.lieferdatum = _parse_date(request.form.get('lieferdatum'))
        herde.lieferant = request.form.get('lieferant', '').strip() or None
        herde.lieferant_vvvo = request.form.get('lieferant_vvvo', '').strip() or None
        herde.anfangsbestand = _parse_int(request.form.get('anfangsbestand'), herde.anfangsbestand)
        herde.aktueller_bestand = _parse_int(request.form.get('aktueller_bestand'), herde.aktueller_bestand)
        herde.stall_nr = request.form.get('stall_nr', '').strip() or None
        herde.stall_flaeche_m2 = _parse_float(request.form.get('stall_flaeche_m2'))
        herde.auslauf_flaeche_m2 = _parse_float(request.form.get('auslauf_flaeche_m2'))
        herde.nest_plaetze = _parse_int(request.form.get('nest_plaetze'))
        herde.erzeuger_code = request.form.get('erzeuger_code', '').strip() or None
        herde.legebeginn = _parse_date(request.form.get('legebeginn'))
        herde.erwartetes_ende = _parse_date(request.form.get('erwartetes_ende'))
        herde.ausstalldatum = _parse_date(request.form.get('ausstalldatum'))
        herde.ist_aktiv = request.form.get('ist_aktiv') == '1'
        herde.bemerkung = request.form.get('bemerkung', '').strip() or None
        db.session.commit()
        flash(f'Herde „{herde.name}" gespeichert.', 'success')
        return redirect(url_for('legehennen.herde_detail', id=herde.id))

    return render_template('legehennen/herde_form.html',
                           herde=herde,
                           haltungsformen=HALTUNGSFORMEN)


@legehennen_bp.route('/herde/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def herde_delete(id):
    """Herde löschen."""
    herde = Herde.query.get_or_404(id)
    name = herde.name
    db.session.delete(herde)
    db.session.commit()
    flash(f'Herde „{name}" gelöscht.', 'success')
    return redirect(url_for('legehennen.index'))


# ── Tagesleistung (Stallbuch) ────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/tagesleistung/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('legehennen', 'create')
def tagesleistung_neu(herde_id):
    """Neue Tagesleistung erfassen."""
    herde = Herde.query.get_or_404(herde_id)

    if request.method == 'POST':
        tl = Tagesleistung(
            herde_id=herde.id,
            datum=_parse_date(request.form.get('datum')) or date.today(),
            eier_gesamt=_parse_int(request.form.get('eier_gesamt'), 0),
            eier_verkaufsfaehig=_parse_int(request.form.get('eier_verkaufsfaehig'), 0),
            eier_knick=_parse_int(request.form.get('eier_knick'), 0),
            eier_bruch=_parse_int(request.form.get('eier_bruch'), 0),
            eier_schmutzig=_parse_int(request.form.get('eier_schmutzig'), 0),
            eier_wind=_parse_int(request.form.get('eier_wind'), 0),
            eier_boden=_parse_int(request.form.get('eier_boden'), 0),
            eigewicht_durchschnitt=_parse_float(request.form.get('eigewicht_durchschnitt')),
            tierbestand=_parse_int(request.form.get('tierbestand'), herde.aktueller_bestand),
            verluste=_parse_int(request.form.get('verluste'), 0),
            verlust_ursache=request.form.get('verlust_ursache', '').strip() or None,
            futterverbrauch_kg=_parse_float(request.form.get('futterverbrauch_kg')),
            wasserverbrauch_l=_parse_float(request.form.get('wasserverbrauch_l')),
            temperatur_stall=_parse_float(request.form.get('temperatur_stall')),
            luftfeuchtigkeit=_parse_float(request.form.get('luftfeuchtigkeit')),
            lichtprogramm_std=_parse_float(request.form.get('lichtprogramm_std')),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        # Bestand aktualisieren bei Verlusten
        verluste = tl.verluste or 0
        if verluste > 0 and herde.aktueller_bestand:
            herde.aktueller_bestand = max(0, herde.aktueller_bestand - verluste)

        db.session.add(tl)
        db.session.commit()
        flash('Tagesleistung erfasst.', 'success')
        return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='stallbuch'))

    return render_template('legehennen/stallbuch_form.html',
                           herde=herde, tagesleistung=None)


@legehennen_bp.route('/tagesleistung/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission('legehennen', 'edit')
def tagesleistung_edit(id):
    """Tagesleistung bearbeiten."""
    tl = Tagesleistung.query.get_or_404(id)
    herde = tl.herde

    if request.method == 'POST':
        tl.datum = _parse_date(request.form.get('datum')) or tl.datum
        tl.eier_gesamt = _parse_int(request.form.get('eier_gesamt'), 0)
        tl.eier_verkaufsfaehig = _parse_int(request.form.get('eier_verkaufsfaehig'), 0)
        tl.eier_knick = _parse_int(request.form.get('eier_knick'), 0)
        tl.eier_bruch = _parse_int(request.form.get('eier_bruch'), 0)
        tl.eier_schmutzig = _parse_int(request.form.get('eier_schmutzig'), 0)
        tl.eier_wind = _parse_int(request.form.get('eier_wind'), 0)
        tl.eier_boden = _parse_int(request.form.get('eier_boden'), 0)
        tl.eigewicht_durchschnitt = _parse_float(request.form.get('eigewicht_durchschnitt'))
        tl.tierbestand = _parse_int(request.form.get('tierbestand'), tl.tierbestand)
        tl.verluste = _parse_int(request.form.get('verluste'), 0)
        tl.verlust_ursache = request.form.get('verlust_ursache', '').strip() or None
        tl.futterverbrauch_kg = _parse_float(request.form.get('futterverbrauch_kg'))
        tl.wasserverbrauch_l = _parse_float(request.form.get('wasserverbrauch_l'))
        tl.temperatur_stall = _parse_float(request.form.get('temperatur_stall'))
        tl.luftfeuchtigkeit = _parse_float(request.form.get('luftfeuchtigkeit'))
        tl.lichtprogramm_std = _parse_float(request.form.get('lichtprogramm_std'))
        tl.bemerkung = request.form.get('bemerkung', '').strip() or None
        db.session.commit()
        flash('Tagesleistung aktualisiert.', 'success')
        return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='stallbuch'))

    return render_template('legehennen/stallbuch_form.html',
                           herde=herde, tagesleistung=tl)


@legehennen_bp.route('/tagesleistung/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def tagesleistung_delete(id):
    """Tagesleistung löschen."""
    tl = Tagesleistung.query.get_or_404(id)
    herde_id = tl.herde_id
    db.session.delete(tl)
    db.session.commit()
    flash('Tagesleistung gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='stallbuch'))


# ── Sortierergebnis (Packstelle) ────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/sortierung/neu', methods=['GET', 'POST'])
@login_required
@requires_permission('sortierergebnis', 'create')
def sortierung_neu(herde_id):
    """Neues Sortierergebnis eintragen."""
    herde = Herde.query.get_or_404(herde_id)

    if request.method == 'POST':
        s = Sortierergebnis(
            herde_id=herde.id,
            datum=_parse_date(request.form.get('datum')) or date.today(),
            eier_gesamt=_parse_int(request.form.get('eier_gesamt'), 0),
            groesse_s=_parse_int(request.form.get('groesse_s'), 0),
            groesse_m=_parse_int(request.form.get('groesse_m'), 0),
            groesse_l=_parse_int(request.form.get('groesse_l'), 0),
            groesse_xl=_parse_int(request.form.get('groesse_xl'), 0),
            aussortiert=_parse_int(request.form.get('aussortiert'), 0),
            bemerkung=request.form.get('bemerkung', '').strip() or None,
        )
        db.session.add(s)
        db.session.commit()
        flash('Sortierergebnis eingetragen.', 'success')
        return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='sortierung'))

    return render_template('legehennen/sortierung_form.html',
                           herde=herde, sortierung=None)


@legehennen_bp.route('/sortierung/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@requires_permission('sortierergebnis', 'edit')
def sortierung_edit(id):
    """Sortierergebnis bearbeiten."""
    s = Sortierergebnis.query.get_or_404(id)
    herde = s.herde

    if request.method == 'POST':
        s.datum = _parse_date(request.form.get('datum')) or s.datum
        s.eier_gesamt = _parse_int(request.form.get('eier_gesamt'), 0)
        s.groesse_s = _parse_int(request.form.get('groesse_s'), 0)
        s.groesse_m = _parse_int(request.form.get('groesse_m'), 0)
        s.groesse_l = _parse_int(request.form.get('groesse_l'), 0)
        s.groesse_xl = _parse_int(request.form.get('groesse_xl'), 0)
        s.aussortiert = _parse_int(request.form.get('aussortiert'), 0)
        s.bemerkung = request.form.get('bemerkung', '').strip() or None
        db.session.commit()
        flash('Sortierergebnis aktualisiert.', 'success')
        return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='sortierung'))

    return render_template('legehennen/sortierung_form.html',
                           herde=herde, sortierung=s)


@legehennen_bp.route('/sortierung/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('sortierergebnis', 'delete')
def sortierung_delete(id):
    """Sortierergebnis löschen."""
    s = Sortierergebnis.query.get_or_404(id)
    herde_id = s.herde_id
    db.session.delete(s)
    db.session.commit()
    flash('Sortierergebnis gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='sortierung'))


# ── Tierarztbesuch ───────────────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/tierarzt/neu', methods=['POST'])
@login_required
@requires_permission('legehennen', 'create')
def tierarzt_neu(herde_id):
    """Tierarztbesuch hinzufügen."""
    herde = Herde.query.get_or_404(herde_id)
    ta = TierarztBesuch(
        herde_id=herde.id,
        datum=_parse_date(request.form.get('datum')) or date.today(),
        tierarzt_name=request.form.get('tierarzt_name', '').strip() or None,
        tierarzt_praxis=request.form.get('tierarzt_praxis', '').strip() or None,
        grund=request.form.get('grund', '').strip() or None,
        diagnose=request.form.get('diagnose', '').strip() or None,
        massnahmen=request.form.get('massnahmen', '').strip() or None,
        naechster_besuch=_parse_date(request.form.get('naechster_besuch')),
        kosten=_parse_float(request.form.get('kosten')),
        bemerkung=request.form.get('bemerkung', '').strip() or None,
    )
    db.session.add(ta)
    db.session.commit()
    flash('Tierarztbesuch eingetragen.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='tierarzt'))


@legehennen_bp.route('/tierarzt/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def tierarzt_delete(id):
    ta = TierarztBesuch.query.get_or_404(id)
    herde_id = ta.herde_id
    db.session.delete(ta)
    db.session.commit()
    flash('Tierarztbesuch gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='tierarzt'))


# ── Impfung ──────────────────────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/impfung/neu', methods=['POST'])
@login_required
@requires_permission('legehennen', 'create')
def impfung_neu(herde_id):
    """Impfung hinzufügen."""
    herde = Herde.query.get_or_404(herde_id)
    imp = Impfung(
        herde_id=herde.id,
        datum=_parse_date(request.form.get('datum')) or date.today(),
        impfstoff=request.form.get('impfstoff', '').strip() or None,
        krankheit=request.form.get('krankheit', '').strip() or None,
        charge=request.form.get('charge', '').strip() or None,
        verabreichungsart=request.form.get('verabreichungsart', '').strip() or None,
        tierarzt=request.form.get('tierarzt', '').strip() or None,
        naechste_impfung=_parse_date(request.form.get('naechste_impfung')),
        bemerkung=request.form.get('bemerkung', '').strip() or None,
    )
    db.session.add(imp)
    db.session.commit()
    flash('Impfung eingetragen.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='tierarzt'))


@legehennen_bp.route('/impfung/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def impfung_delete(id):
    imp = Impfung.query.get_or_404(id)
    herde_id = imp.herde_id
    db.session.delete(imp)
    db.session.commit()
    flash('Impfung gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='tierarzt'))


# ── Medikament ───────────────────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/medikament/neu', methods=['POST'])
@login_required
@requires_permission('legehennen', 'create')
def medikament_neu(herde_id):
    """Medikamentenbehandlung hinzufügen."""
    herde = Herde.query.get_or_404(herde_id)
    med = MedikamentBehandlung(
        herde_id=herde.id,
        beginn=_parse_date(request.form.get('beginn')) or date.today(),
        ende=_parse_date(request.form.get('ende')),
        medikament_name=request.form.get('medikament_name', '').strip(),
        wirkstoff=request.form.get('wirkstoff', '').strip() or None,
        typ=request.form.get('typ', '').strip() or None,
        charge=request.form.get('charge', '').strip() or None,
        dosierung=request.form.get('dosierung', '').strip() or None,
        verabreichungsart=request.form.get('verabreichungsart', '').strip() or None,
        diagnose=request.form.get('diagnose', '').strip() or None,
        tierarzt=request.form.get('tierarzt', '').strip() or None,
        anzahl_tiere=_parse_int(request.form.get('anzahl_tiere')),
        wartezeit_tage=_parse_int(request.form.get('wartezeit_tage'), 0),
        ist_antibiotikum=request.form.get('ist_antibiotikum') == '1',
        beleg_nr=request.form.get('beleg_nr', '').strip() or None,
        bemerkung=request.form.get('bemerkung', '').strip() or None,
    )
    med.berechne_wartezeit_ende()
    db.session.add(med)
    db.session.commit()
    flash('Medikamentenbehandlung eingetragen.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='tierarzt'))


@legehennen_bp.route('/medikament/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def medikament_delete(id):
    med = MedikamentBehandlung.query.get_or_404(id)
    herde_id = med.herde_id
    db.session.delete(med)
    db.session.commit()
    flash('Medikamentenbehandlung gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='tierarzt'))


# ── Salmonellenprobe ─────────────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/salmonellen/neu', methods=['POST'])
@login_required
@requires_permission('legehennen', 'create')
def salmonellen_neu(herde_id):
    """Salmonellenprobe hinzufügen."""
    herde = Herde.query.get_or_404(herde_id)
    sp = SalmonellenProbe(
        herde_id=herde.id,
        probenahme_datum=_parse_date(request.form.get('probenahme_datum')) or date.today(),
        probenart=request.form.get('probenart', '').strip() or None,
        labor=request.form.get('labor', '').strip() or None,
        ergebnis=request.form.get('ergebnis', '').strip() or None,
        ergebnis_datum=_parse_date(request.form.get('ergebnis_datum')),
        massnahmen=request.form.get('massnahmen', '').strip() or None,
        bemerkung=request.form.get('bemerkung', '').strip() or None,
    )
    db.session.add(sp)
    db.session.commit()
    flash('Salmonellenprobe eingetragen.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='salmonellen'))


@legehennen_bp.route('/salmonellen/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def salmonellen_delete(id):
    sp = SalmonellenProbe.query.get_or_404(id)
    herde_id = sp.herde_id
    db.session.delete(sp)
    db.session.commit()
    flash('Salmonellenprobe gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='salmonellen'))


# ── Futterlieferung ──────────────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/futter/neu', methods=['POST'])
@login_required
@requires_permission('legehennen', 'create')
def futter_neu(herde_id):
    """Futterlieferung hinzufügen."""
    herde = Herde.query.get_or_404(herde_id)
    fl = FutterLieferung(
        herde_id=herde.id,
        datum=_parse_date(request.form.get('datum')) or date.today(),
        futtermittel=request.form.get('futtermittel', '').strip() or None,
        lieferant=request.form.get('lieferant', '').strip() or None,
        menge_kg=_parse_float(request.form.get('menge_kg')),
        charge=request.form.get('charge', '').strip() or None,
        preis=_parse_float(request.form.get('preis')),
        bemerkung=request.form.get('bemerkung', '').strip() or None,
    )
    db.session.add(fl)
    db.session.commit()
    flash('Futterlieferung eingetragen.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='futter'))


@legehennen_bp.route('/futter/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def futter_delete(id):
    fl = FutterLieferung.query.get_or_404(id)
    herde_id = fl.herde_id
    db.session.delete(fl)
    db.session.commit()
    flash('Futterlieferung gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='futter'))


# ── Ereignis ─────────────────────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/ereignis/neu', methods=['POST'])
@login_required
@requires_permission('legehennen', 'create')
def ereignis_neu(herde_id):
    """Ereignis hinzufügen."""
    herde = Herde.query.get_or_404(herde_id)
    er = HerdeEreignis(
        herde_id=herde.id,
        datum=_parse_date(request.form.get('datum')) or date.today(),
        kategorie=request.form.get('kategorie', '').strip() or None,
        beschreibung=request.form.get('beschreibung', '').strip() or None,
        massnahmen=request.form.get('massnahmen', '').strip() or None,
        bemerkung=request.form.get('bemerkung', '').strip() or None,
    )
    db.session.add(er)
    db.session.commit()
    flash('Ereignis eingetragen.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde.id, tab='ereignisse'))


@legehennen_bp.route('/ereignis/<int:id>/delete', methods=['POST'])
@login_required
@requires_permission('legehennen', 'delete')
def ereignis_delete(id):
    er = HerdeEreignis.query.get_or_404(id)
    herde_id = er.herde_id
    db.session.delete(er)
    db.session.commit()
    flash('Ereignis gelöscht.', 'success')
    return redirect(url_for('legehennen.herde_detail', id=herde_id, tab='ereignisse'))


# ── JSON APIs für Charts ─────────────────────────────────────────

@legehennen_bp.route('/herde/<int:herde_id>/api/legekurve')
@login_required
@requires_permission('legehennen', 'view')
def api_legekurve(herde_id):
    """JSON-Daten für Legekurve (Chart.js)."""
    herde = Herde.query.get_or_404(herde_id)
    tagesleistungen = herde.tagesleistungen.order_by(Tagesleistung.datum.asc()).all()

    labels = []
    legerate = []
    eigewicht = []
    verluste_kum = []
    verluste_sum = 0

    for tl in tagesleistungen:
        labels.append(tl.datum.strftime('%d.%m.%Y'))
        legerate.append(tl.legerate_prozent)
        eigewicht.append(float(tl.eigewicht_durchschnitt) if tl.eigewicht_durchschnitt else None)
        verluste_sum += (tl.verluste or 0)
        verluste_kum.append(verluste_sum)

    return jsonify({
        'labels': labels,
        'legerate': legerate,
        'eigewicht': eigewicht,
        'verluste_kumuliert': verluste_kum,
    })


@legehennen_bp.route('/herde/<int:herde_id>/api/sortierung')
@login_required
@requires_permission('legehennen', 'view')
def api_sortierung(herde_id):
    """JSON-Daten für Eigrößen-Entwicklung (Chart.js)."""
    herde = Herde.query.get_or_404(herde_id)
    sortierungen = herde.sortierergebnisse.order_by(Sortierergebnis.datum.asc()).all()

    labels = []
    anteil_s = []
    anteil_m = []
    anteil_l = []
    anteil_xl = []

    for s in sortierungen:
        labels.append(s.datum.strftime('%d.%m.%Y'))
        anteil_s.append(s.anteil_s)
        anteil_m.append(s.anteil_m)
        anteil_l.append(s.anteil_l)
        anteil_xl.append(s.anteil_xl)

    return jsonify({
        'labels': labels,
        'anteil_s': anteil_s,
        'anteil_m': anteil_m,
        'anteil_l': anteil_l,
        'anteil_xl': anteil_xl,
    })


# ── Packstelle-Einstieg (für Rolle packstelle) ──────────────────

@legehennen_bp.route('/packstelle')
@login_required
@requires_permission('sortierergebnis', 'view')
def packstelle_index():
    """Packstelle-Startseite: nur aktive Herden zur Sortierergebnis-Eingabe."""
    herden = Herde.query.filter_by(ist_aktiv=True).order_by(Herde.name).all()
    return render_template('legehennen/packstelle_index.html',
                           herden=herden,
                           haltungsformen=HALTUNGSFORMEN)
