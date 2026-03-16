"""
Ackerbau-Blueprint.

Modul 1 (modul_ackerbau): Schlagkartei, Spritztagebuch, Düngerplaner
Modul 2 (modul_ackerbau_pro): NAPV-Bedarfsermittlung, Bodenuntersuchung,
                               170 kg N/ha Bilanz, Rote Gebiete, Sperrfristen
"""
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.extensions import db
from app.models.rollen import hat_berechtigung, hat_modul_zugriff
from app.models.ackerbau import (
    Schlag, SchlagKultur, Spritzmittel, Spritzung, Duengung,
    Bodenuntersuchung, Duengebedarfsermittlung, Tierbestand,
    EPPO_KULTUREN, SPRITZMITTEL_KATEGORIEN, SPRITZMITTEL_EINHEITEN,
    BBCH_STADIEN, DUENGER_ARTEN, DUENGER_EINHEITEN, BODENARTEN,
    AUSBRINGVERFAHREN, TIERKATEGORIEN_N,
)

ackerbau_bp = Blueprint('ackerbau', __name__, url_prefix='/ackerbau')


def _check_ackerbau():
    """Zugriff auf Modul 1 prüfen."""
    if not hat_modul_zugriff(current_user, 'ackerbau'):
        abort(403)


def _check_ackerbau_pro():
    """Zugriff auf Modul 2 (Pro) prüfen."""
    if not hat_modul_zugriff(current_user, 'ackerbau_pro'):
        abort(403)


# ---------------------------------------------------------------------------
# Schläge
# ---------------------------------------------------------------------------

@ackerbau_bp.route('/')
@login_required
def index():
    _check_ackerbau()
    schlaege = Schlag.query.filter_by(aktiv=True).order_by(Schlag.name).all()
    return render_template('ackerbau/index.html', schlaege=schlaege)


@ackerbau_bp.route('/schlaege')
@login_required
def schlag_liste():
    _check_ackerbau()
    alle = Schlag.query.order_by(Schlag.aktiv.desc(), Schlag.name).all()
    return render_template('ackerbau/schlag_liste.html', schlaege=alle)


@ackerbau_bp.route('/schlaege/neu', methods=['GET', 'POST'])
@login_required
def schlag_neu():
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'create'):
        abort(403)
    if request.method == 'POST':
        schlag = Schlag(
            name=request.form['name'].strip(),
            flaeche_ha=request.form.get('flaeche_ha') or None,
            feldstueck_nr=request.form.get('feldstueck_nr', '').strip() or None,
            invekos_flaeche=request.form.get('invekos_flaeche') or None,
            bodenart=request.form.get('bodenart', '').strip() or None,
            notizen=request.form.get('notizen', '').strip() or None,
        )
        db.session.add(schlag)
        db.session.commit()
        flash(f'Schlag „{schlag.name}" angelegt.', 'success')
        return redirect(url_for('ackerbau.schlag_detail', schlag_id=schlag.id))
    return render_template('ackerbau/schlag_form.html', schlag=None, bodenarten=BODENARTEN)


@ackerbau_bp.route('/schlaege/<int:schlag_id>')
@login_required
def schlag_detail(schlag_id):
    _check_ackerbau()
    schlag = Schlag.query.get_or_404(schlag_id)
    kulturen = schlag.kulturen.all()
    spritzungen = schlag.spritzungen.order_by(Spritzung.datum.desc()).limit(20).all()
    duengungen = schlag.duengungen.order_by(Duengung.datum.desc()).limit(20).all()
    bodenuntersuchungen = []
    if hat_modul_zugriff(current_user, 'ackerbau_pro'):
        bodenuntersuchungen = schlag.bodenuntersuchungen.order_by(
            Bodenuntersuchung.datum.desc()).all()
    return render_template('ackerbau/schlag_detail.html',
                           schlag=schlag,
                           kulturen=kulturen,
                           spritzungen=spritzungen,
                           duengungen=duengungen,
                           bodenuntersuchungen=bodenuntersuchungen)


@ackerbau_bp.route('/schlaege/<int:schlag_id>/bearbeiten', methods=['GET', 'POST'])
@login_required
def schlag_bearbeiten(schlag_id):
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'edit'):
        abort(403)
    schlag = Schlag.query.get_or_404(schlag_id)
    if request.method == 'POST':
        schlag.name = request.form['name'].strip()
        schlag.flaeche_ha = request.form.get('flaeche_ha') or None
        schlag.feldstueck_nr = request.form.get('feldstueck_nr', '').strip() or None
        schlag.invekos_flaeche = request.form.get('invekos_flaeche') or None
        schlag.bodenart = request.form.get('bodenart', '').strip() or None
        schlag.notizen = request.form.get('notizen', '').strip() or None
        db.session.commit()
        flash('Schlag aktualisiert.', 'success')
        return redirect(url_for('ackerbau.schlag_detail', schlag_id=schlag.id))
    return render_template('ackerbau/schlag_form.html', schlag=schlag, bodenarten=BODENARTEN)


# ---------------------------------------------------------------------------
# Kulturen
# ---------------------------------------------------------------------------

@ackerbau_bp.route('/schlaege/<int:schlag_id>/kulturen/neu', methods=['GET', 'POST'])
@login_required
def kultur_neu(schlag_id):
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'create'):
        abort(403)
    schlag = Schlag.query.get_or_404(schlag_id)
    if request.method == 'POST':
        kultur_code = request.form['kultur_code']
        kultur_name = dict(EPPO_KULTUREN).get(kultur_code, request.form.get('kultur_name', kultur_code))
        kultur = SchlagKultur(
            schlag_id=schlag.id,
            kultur_code=kultur_code,
            kultur_name=kultur_name,
            aussaat_datum=date.fromisoformat(request.form['aussaat_datum']),
            ernte_datum=date.fromisoformat(request.form['ernte_datum']) if request.form.get('ernte_datum') else None,
            bemerkungen=request.form.get('bemerkungen', '').strip() or None,
        )
        db.session.add(kultur)
        db.session.commit()
        flash(f'Kultur „{kultur.kultur_name}" eingetragen.', 'success')
        return redirect(url_for('ackerbau.schlag_detail', schlag_id=schlag.id))
    return render_template('ackerbau/kultur_form.html', schlag=schlag, eppo_kulturen=EPPO_KULTUREN)


@ackerbau_bp.route('/kulturen/<int:kultur_id>/ernte', methods=['POST'])
@login_required
def kultur_ernte(kultur_id):
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'edit'):
        abort(403)
    kultur = SchlagKultur.query.get_or_404(kultur_id)
    ernte_datum = request.form.get('ernte_datum')
    kultur.ernte_datum = date.fromisoformat(ernte_datum) if ernte_datum else date.today()
    db.session.commit()
    flash(f'Ernte von „{kultur.kultur_name}" eingetragen.', 'success')
    return redirect(url_for('ackerbau.schlag_detail', schlag_id=kultur.schlag_id))


# ---------------------------------------------------------------------------
# Spritzmittel-Stammdaten
# ---------------------------------------------------------------------------

@ackerbau_bp.route('/spritzmittel')
@login_required
def spritzmittel_liste():
    _check_ackerbau()
    alle = Spritzmittel.query.order_by(Spritzmittel.aktiv.desc(), Spritzmittel.name).all()
    return render_template('ackerbau/spritzmittel_liste.html', spritzmittel=alle)


@ackerbau_bp.route('/spritzmittel/neu', methods=['GET', 'POST'])
@login_required
def spritzmittel_neu():
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'create'):
        abort(403)
    if request.method == 'POST':
        sm = Spritzmittel(
            name=request.form['name'].strip(),
            wirkstoff=request.form.get('wirkstoff', '').strip() or None,
            zulassungsnummer=request.form.get('zulassungsnummer', '').strip() or None,
            registernummer=request.form.get('registernummer', '').strip() or None,
            kategorie=request.form.get('kategorie', '').strip() or None,
            einheit=request.form.get('einheit', 'l/ha'),
        )
        db.session.add(sm)
        db.session.commit()
        flash(f'Spritzmittel „{sm.name}" angelegt.', 'success')
        return redirect(url_for('ackerbau.spritzmittel_liste'))
    return render_template('ackerbau/spritzmittel_form.html',
                           sm=None,
                           kategorien=SPRITZMITTEL_KATEGORIEN,
                           einheiten=SPRITZMITTEL_EINHEITEN)


@ackerbau_bp.route('/spritzmittel/<int:sm_id>/bearbeiten', methods=['GET', 'POST'])
@login_required
def spritzmittel_bearbeiten(sm_id):
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'edit'):
        abort(403)
    sm = Spritzmittel.query.get_or_404(sm_id)
    if request.method == 'POST':
        sm.name = request.form['name'].strip()
        sm.wirkstoff = request.form.get('wirkstoff', '').strip() or None
        sm.zulassungsnummer = request.form.get('zulassungsnummer', '').strip() or None
        sm.registernummer = request.form.get('registernummer', '').strip() or None
        sm.kategorie = request.form.get('kategorie', '').strip() or None
        sm.einheit = request.form.get('einheit', 'l/ha')
        sm.aktiv = 'aktiv' in request.form
        db.session.commit()
        flash('Spritzmittel aktualisiert.', 'success')
        return redirect(url_for('ackerbau.spritzmittel_liste'))
    return render_template('ackerbau/spritzmittel_form.html',
                           sm=sm,
                           kategorien=SPRITZMITTEL_KATEGORIEN,
                           einheiten=SPRITZMITTEL_EINHEITEN)


# ---------------------------------------------------------------------------
# Spritztagebuch
# ---------------------------------------------------------------------------

@ackerbau_bp.route('/spritztagebuch')
@login_required
def spritztagebuch():
    _check_ackerbau()
    jahr = request.args.get('jahr', date.today().year, type=int)
    eintraege = (Spritzung.query
                 .join(Schlag)
                 .filter(db.extract('year', Spritzung.datum) == jahr)
                 .order_by(Spritzung.datum.desc())
                 .all())
    return render_template('ackerbau/spritztagebuch.html',
                           eintraege=eintraege,
                           jahr=jahr)


@ackerbau_bp.route('/schlaege/<int:schlag_id>/spritzung/neu', methods=['GET', 'POST'])
@login_required
def spritzung_neu(schlag_id):
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'create'):
        abort(403)
    schlag = Schlag.query.get_or_404(schlag_id)
    if request.method == 'POST':
        sm_id = request.form.get('spritzmittel_id', type=int)
        if not sm_id:
            flash('Bitte ein Spritzmittel auswählen.', 'warning')
        else:
            spritzung = Spritzung(
                schlag_id=schlag.id,
                schlag_kultur_id=request.form.get('schlag_kultur_id', type=int) or None,
                spritzmittel_id=sm_id,
                datum=date.fromisoformat(request.form['datum']),
                uhrzeit=datetime.strptime(request.form['uhrzeit'], '%H:%M').time() if request.form.get('uhrzeit') else None,
                bbch_stadium=request.form.get('bbch_stadium', '').strip() or None,
                aufwandmenge=request.form['aufwandmenge'],
                invekos_flaeche=request.form.get('invekos_flaeche') or None,
                behandelte_flaeche=request.form.get('behandelte_flaeche') or None,
                bemerkungen=request.form.get('bemerkungen', '').strip() or None,
            )
            db.session.add(spritzung)
            db.session.commit()
            flash('Spritzung eingetragen.', 'success')
            return redirect(url_for('ackerbau.schlag_detail', schlag_id=schlag.id))
    spritzmittel = Spritzmittel.query.filter_by(aktiv=True).order_by(Spritzmittel.name).all()
    kulturen = schlag.kulturen.all()
    return render_template('ackerbau/spritzung_form.html',
                           schlag=schlag,
                           spritzmittel=spritzmittel,
                           kulturen=kulturen,
                           bbch_stadien=BBCH_STADIEN,
                           heute=date.today())


# ---------------------------------------------------------------------------
# Düngerplaner (Modul 1)
# ---------------------------------------------------------------------------

@ackerbau_bp.route('/duengerplaner')
@login_required
def duengerplaner():
    _check_ackerbau()
    jahr = request.args.get('jahr', date.today().year, type=int)
    duengungen = (Duengung.query
                  .join(Schlag)
                  .filter(db.extract('year', Duengung.datum) == jahr)
                  .order_by(Duengung.datum.desc())
                  .all())
    return render_template('ackerbau/duengerplaner.html', duengungen=duengungen, jahr=jahr)


@ackerbau_bp.route('/schlaege/<int:schlag_id>/duengung/neu', methods=['GET', 'POST'])
@login_required
def duengung_neu(schlag_id):
    _check_ackerbau()
    if not hat_berechtigung(current_user, 'ackerbau', 'create'):
        abort(403)
    schlag = Schlag.query.get_or_404(schlag_id)
    if request.method == 'POST':
        menge = float(request.form['menge'])
        n_gehalt = float(request.form['n_gehalt']) if request.form.get('n_gehalt') else None
        p_gehalt = float(request.form['p_gehalt']) if request.form.get('p_gehalt') else None
        k_gehalt = float(request.form['k_gehalt']) if request.form.get('k_gehalt') else None
        flaeche = float(request.form['behandelte_flaeche']) if request.form.get('behandelte_flaeche') else None

        d = Duengung(
            schlag_id=schlag.id,
            kultur_id=request.form.get('kultur_id', type=int) or None,
            datum=date.fromisoformat(request.form['datum']),
            duenger_art=request.form['duenger_art'],
            duenger_name=request.form.get('duenger_name', '').strip() or None,
            n_gehalt=n_gehalt,
            p_gehalt=p_gehalt,
            k_gehalt=k_gehalt,
            menge=menge,
            einheit=request.form.get('einheit', 'kg/ha'),
            behandelte_flaeche=flaeche,
            n_ausgebracht=round(menge * n_gehalt, 2) if n_gehalt else None,
            p_ausgebracht=round(menge * p_gehalt, 2) if p_gehalt else None,
            k_ausgebracht=round(menge * k_gehalt, 2) if k_gehalt else None,
            ausbringverfahren=request.form.get('ausbringverfahren', '').strip() or None,
            einarbeitung='einarbeitung' in request.form,
            bemerkungen=request.form.get('bemerkungen', '').strip() or None,
        )
        db.session.add(d)
        db.session.commit()
        flash('Düngegabe eingetragen.', 'success')
        return redirect(url_for('ackerbau.schlag_detail', schlag_id=schlag.id))
    kulturen = schlag.kulturen.all()
    return render_template('ackerbau/duengung_form.html',
                           schlag=schlag,
                           kulturen=kulturen,
                           duenger_arten=DUENGER_ARTEN,
                           duenger_einheiten=DUENGER_EINHEITEN,
                           ausbringverfahren=AUSBRINGVERFAHREN,
                           heute=date.today())


# ---------------------------------------------------------------------------
# Pro-Modul: Bodenuntersuchung
# ---------------------------------------------------------------------------

@ackerbau_bp.route('/schlaege/<int:schlag_id>/bodenuntersuchung/neu', methods=['GET', 'POST'])
@login_required
def bodenuntersuchung_neu(schlag_id):
    _check_ackerbau_pro()
    if not hat_berechtigung(current_user, 'ackerbau_pro', 'create'):
        abort(403)
    schlag = Schlag.query.get_or_404(schlag_id)
    if request.method == 'POST':
        bu = Bodenuntersuchung(
            schlag_id=schlag.id,
            datum=date.fromisoformat(request.form['datum']),
            labor=request.form.get('labor', '').strip() or None,
            ph_wert=request.form.get('ph_wert') or None,
            p_gehalt=request.form.get('p_gehalt') or None,
            k_gehalt=request.form.get('k_gehalt') or None,
            mg_gehalt=request.form.get('mg_gehalt') or None,
            humus=request.form.get('humus') or None,
            p_klasse=request.form.get('p_klasse', '').strip() or None,
            k_klasse=request.form.get('k_klasse', '').strip() or None,
            mg_klasse=request.form.get('mg_klasse', '').strip() or None,
            bemerkungen=request.form.get('bemerkungen', '').strip() or None,
        )
        db.session.add(bu)
        db.session.commit()
        flash('Bodenuntersuchung eingetragen.', 'success')
        return redirect(url_for('ackerbau.schlag_detail', schlag_id=schlag.id))
    return render_template('ackerbau/bodenuntersuchung_form.html',
                           schlag=schlag,
                           heute=date.today())


# ---------------------------------------------------------------------------
# Pro-Modul: NAPV-Düngebedarfsermittlung
# ---------------------------------------------------------------------------

# N-Bedarf-Tabelle (vereinfacht, kg N/ha bei Normertrag)
NAPV_N_BEDARF = {
    'TRZAW': {'basis': 160, 'faktor_dt': 3.0},   # Winterweizen
    'TRZAS': {'basis': 130, 'faktor_dt': 3.0},   # Sommerweizen
    'HORVW': {'basis': 110, 'faktor_dt': 2.5},   # Wintergerste
    'HORVS': {'basis': 100, 'faktor_dt': 2.5},   # Sommergerste
    'ZEAMX': {'basis': 170, 'faktor_dt': 2.8},   # Mais
    'BRSNN': {'basis': 200, 'faktor_dt': 4.0},   # Winterraps
    'GLXMA': {'basis': 0,   'faktor_dt': 0},     # Soja (N-Fixierung)
    'HELAN': {'basis': 100, 'faktor_dt': 2.5},   # Sonnenblume
    'AVESA': {'basis': 100, 'faktor_dt': 2.5},   # Hafer
    'SECCE': {'basis': 120, 'faktor_dt': 2.5},   # Roggen
    'TTLSP': {'basis': 130, 'faktor_dt': 2.5},   # Triticale
    'BEAVD': {'basis': 150, 'faktor_dt': 1.8},   # Zuckerrübe
    'SOLTU': {'basis': 160, 'faktor_dt': 1.5},   # Kartoffel
    'MEDSA': {'basis': 0,   'faktor_dt': 0},     # Luzerne (N-Fixierung)
}

# Humus-N-Nachlieferung (kg N/ha)
HUMUS_N_NACHLIEFERUNG = {
    'unter 1%': 20,
    '1-2%': 40,
    '2-4%': 60,
    'über 4%': 80,
}

# Vorfrucht-N-Gutschrift (kg N/ha)
VORFRUCHT_N_GUTSCHRIFT = {
    'Getreide': 0,
    'Mais': 0,
    'Raps': 20,
    'Leguminosen (Erbse, Bohne)': 40,
    'Klee/Luzerne 1 Jahr': 60,
    'Klee/Luzerne mehrjährig': 100,
    'Feldgemüse': 30,
    'Zuckerrübe': 20,
}


@ackerbau_bp.route('/bedarf/<int:schlag_id>/start', methods=['GET', 'POST'])
@login_required
def bedarf_start(schlag_id):
    """Schritt 1: Kultur und Ertragsziel."""
    _check_ackerbau_pro()
    schlag = Schlag.query.get_or_404(schlag_id)
    if request.method == 'POST':
        kultur_code = request.form.get('kultur_code', '')
        ertragsziel = float(request.form.get('ertragsziel_dt_ha', 0) or 0)
        tabelle = NAPV_N_BEDARF.get(kultur_code, {})
        n_brutto = tabelle.get('basis', 0) + ertragsziel * tabelle.get('faktor_dt', 0)

        # Vorläufig speichern
        dbe = Duengebedarfsermittlung(
            schlag_id=schlag.id,
            jahr=date.today().year,
            ertragsziel_dt_ha=ertragsziel,
            n_bedarf_brutto=round(n_brutto, 1),
            ist_rotes_gebiet='rotes_gebiet' in request.form,
        )
        # Kultur aus aktiver Schlagkultur oder gewähltem Code
        if schlag.aktive_kultur and schlag.aktive_kultur.kultur_code == kultur_code:
            dbe.kultur_id = schlag.aktive_kultur.id
        db.session.add(dbe)
        db.session.commit()
        return redirect(url_for('ackerbau.bedarf_boden', dbe_id=dbe.id))

    aktive_kultur = schlag.aktive_kultur
    return render_template('ackerbau/bedarf_start.html',
                           schlag=schlag,
                           aktive_kultur=aktive_kultur,
                           eppo_kulturen=EPPO_KULTUREN,
                           napv_tabelle=NAPV_N_BEDARF)


@ackerbau_bp.route('/bedarf/<int:dbe_id>/boden', methods=['GET', 'POST'])
@login_required
def bedarf_boden(dbe_id):
    """Schritt 2: Boden- und Vorfruchtdaten."""
    _check_ackerbau_pro()
    dbe = Duengebedarfsermittlung.query.get_or_404(dbe_id)
    if request.method == 'POST':
        humus_klasse = request.form.get('humus_klasse', 'unter 1%')
        vorfrucht = request.form.get('vorfrucht', 'Getreide')
        n_wirtschaft = float(request.form.get('n_wirtschaft', 0) or 0)

        dbe.n_nachlieferung_boden = HUMUS_N_NACHLIEFERUNG.get(humus_klasse, 0)
        dbe.n_aus_vorfrucht = VORFRUCHT_N_GUTSCHRIFT.get(vorfrucht, 0)
        dbe.n_aus_wirtschaft = n_wirtschaft

        # Nettobedarf berechnen
        abzug = dbe.n_nachlieferung_boden + dbe.n_aus_vorfrucht + dbe.n_aus_wirtschaft
        n_netto = max(0, float(dbe.n_bedarf_brutto or 0) - abzug)

        # Rotes Gebiet: 20% Reduktion
        if dbe.ist_rotes_gebiet:
            n_netto = n_netto * (1 - float(dbe.reduktion_rotes_gebiet or 20) / 100)

        dbe.n_bedarf_netto = round(n_netto, 1)
        dbe.n_mineraldung_empfehlung = round(n_netto, 1)
        db.session.commit()
        return redirect(url_for('ackerbau.bedarf_ergebnis', dbe_id=dbe.id))

    letzte_bu = (Bodenuntersuchung.query
                 .filter_by(schlag_id=dbe.schlag_id)
                 .order_by(Bodenuntersuchung.datum.desc())
                 .first())
    return render_template('ackerbau/bedarf_boden.html',
                           dbe=dbe,
                           letzte_bu=letzte_bu,
                           humus_klassen=list(HUMUS_N_NACHLIEFERUNG.keys()),
                           vorfruchte=list(VORFRUCHT_N_GUTSCHRIFT.keys()))


@ackerbau_bp.route('/bedarf/<int:dbe_id>/ergebnis')
@login_required
def bedarf_ergebnis(dbe_id):
    """Schritt 3: Ergebnis und Empfehlung."""
    _check_ackerbau_pro()
    dbe = Duengebedarfsermittlung.query.get_or_404(dbe_id)
    return render_template('ackerbau/bedarf_ergebnis.html', dbe=dbe)


# ---------------------------------------------------------------------------
# Pro-Modul: 170 kg N/ha Bilanz (Tierbestand)
# ---------------------------------------------------------------------------

@ackerbau_bp.route('/n-bilanz')
@login_required
def n_bilanz():
    _check_ackerbau_pro()
    jahr = request.args.get('jahr', date.today().year, type=int)

    from app.models.betrieb import Betrieb
    betrieb = Betrieb.query.first()

    tierbestaende = (Tierbestand.query
                     .filter_by(betrieb_id=betrieb.id if betrieb else 0, jahr=jahr)
                     .all())

    # Gesamtfläche aller Schläge
    schlaege = Schlag.query.filter_by(aktiv=True).all()
    gesamt_ha = sum(float(s.flaeche_ha or 0) for s in schlaege)

    # N-Anfall gesamt
    n_anfall_gesamt = sum(float(t.n_anfall_jahr or 0) for t in tierbestaende)
    n_je_ha = round(n_anfall_gesamt / gesamt_ha, 1) if gesamt_ha > 0 else 0

    # Ampel-Status
    if n_je_ha <= 130:
        ampel = 'success'
    elif n_je_ha <= 170:
        ampel = 'warning'
    else:
        ampel = 'danger'

    # Vorschläge aus Tierhaltungsmodulen
    modul_vorschlaege = _get_tierhaltung_vorschlaege(betrieb, tierbestaende)

    return render_template('ackerbau/n_bilanz.html',
                           jahr=jahr,
                           tierbestaende=tierbestaende,
                           schlaege=schlaege,
                           gesamt_ha=gesamt_ha,
                           n_anfall_gesamt=n_anfall_gesamt,
                           n_je_ha=n_je_ha,
                           ampel=ampel,
                           limit_170=170,
                           modul_vorschlaege=modul_vorschlaege)


def _get_tierhaltung_vorschlaege(betrieb, bestehende_eintraege):
    """
    Liest Tierbestandsdaten aus Milchvieh- und Legehennen-Modul
    und schlägt fehlende Tierbestand-Einträge vor.
    """
    vorschlaege = []
    if not betrieb:
        return vorschlaege

    bestehende_kategorien = {t.tier_kategorie for t in bestehende_eintraege}

    # Milchvieh-Modul
    try:
        from app.models.milchvieh import Rind
        from app.models.rollen import ist_modul_lizenziert
        if ist_modul_lizenziert('milchvieh'):
            milchkuehe = Rind.query.filter_by(
                status='aktiv', nutzungsart='Milch'
            ).filter(Rind.geschlecht == 'W').count()
            if milchkuehe > 0 and 'Milchkuh 4000–6000 l' not in bestehende_kategorien:
                vorschlaege.append({
                    'kategorie': 'Milchkuh 4000–6000 l',
                    'anzahl': milchkuehe,
                    'quelle': 'Milchvieh-Modul (aktive Milchkühe)',
                })
    except Exception:
        pass

    # Legehennen-Modul
    try:
        from app.models.legehennen import Herde
        from app.models.rollen import ist_modul_lizenziert
        if ist_modul_lizenziert('legehennen'):
            aktive_herden = Herde.query.filter_by(ist_aktiv=True).all()
            gesamt_hennen = sum(h.aktueller_bestand or h.anfangsbestand or 0 for h in aktive_herden)
            if gesamt_hennen > 0 and 'Legehenne' not in bestehende_kategorien:
                vorschlaege.append({
                    'kategorie': 'Legehenne',
                    'anzahl': gesamt_hennen,
                    'quelle': f'Legehennen-Modul ({len(aktive_herden)} aktive Herde(n))',
                })
    except Exception:
        pass

    return vorschlaege


@ackerbau_bp.route('/n-bilanz/tierbestand/neu', methods=['GET', 'POST'])
@login_required
def tierbestand_neu():
    _check_ackerbau_pro()
    if not hat_berechtigung(current_user, 'ackerbau_pro', 'create'):
        abort(403)
    from app.models.betrieb import Betrieb
    betrieb = Betrieb.query.first()
    if request.method == 'POST':
        tier_kat = request.form['tier_kategorie']
        anzahl = float(request.form['anzahl'])
        n_je_tier = TIERKATEGORIEN_N.get(tier_kat, 0)
        n_anfall = round(anzahl * n_je_tier, 1)

        tb = Tierbestand(
            betrieb_id=betrieb.id,
            jahr=int(request.form.get('jahr', date.today().year)),
            tier_kategorie=tier_kat,
            haltungsform=request.form.get('haltungsform', '').strip() or None,
            anzahl=anzahl,
            n_anfall_jahr=n_anfall,
            n_feldfallend=round(n_anfall * 0.75, 1),  # 75% feldfallend (vereinfacht)
            bemerkungen=request.form.get('bemerkungen', '').strip() or None,
        )
        try:
            db.session.add(tb)
            db.session.commit()
            flash('Tierbestand eingetragen.', 'success')
        except Exception:
            db.session.rollback()
            flash('Fehler: Dieser Eintrag existiert bereits.', 'danger')
        return redirect(url_for('ackerbau.n_bilanz'))
    vorausgefuellt_kategorie = request.args.get('kategorie', '')
    vorausgefuellt_anzahl = request.args.get('anzahl', '')
    return render_template('ackerbau/tierbestand_form.html',
                           tierkategorien=list(TIERKATEGORIEN_N.keys()),
                           heute_jahr=date.today().year,
                           vorausgefuellt_kategorie=vorausgefuellt_kategorie,
                           vorausgefuellt_anzahl=vorausgefuellt_anzahl)
