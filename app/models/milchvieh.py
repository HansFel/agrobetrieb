"""
Milchvieh-Modul – Datenmodelle (Phase 1 + 2).

Bestandsregister, Tierbewegungen, TAMG-Arzneimitteldokumentation
und Impfungen für Milchviehhalter.

Gesetzliche Grundlagen (AT):
- Tierkennzeichnungsgesetz (TKG) / Rinderkennzeichnungsverordnung
- AMA Bestandsregister (MeldeV RIN) - 7 Tage Meldepflicht
- TAMG (Tierarzneimittelgesetz) - Behandlungsjournal
- Lebensmittelsicherheits- und Verbraucherschutzgesetz (LMSVG)
"""
from datetime import datetime, date, timedelta
from app.extensions import db


# === Konstanten ===

RIND_GESCHLECHT = {
    'M': 'Männlich',
    'W': 'Weiblich',
}

RIND_NUTZUNGSART = [
    'Milch',
    'Mast',
    'Zucht',
    'Gemischt',
]

RIND_STATUS = [
    'aktiv',
    'abgegangen',
    'verendet',
    'geschlachtet',
]

RASSEN_MILCH = [
    'Braunvieh',
    'Fleckvieh (Simmental)',
    'Holstein Friesian',
    'Jersey',
    'Montbéliarde',
    'Normande',
    'Red Holstein',
    'Pinzgauer',
    'Tiroler Grauvieh',
    'Murbodner',
    'Sonstige',
]

TIERBEWEGUNG_TYPEN = {
    'geburt': 'Geburt',
    'zukauf': 'Zukauf / Zugang',
    'abgang_verkauf': 'Abgang Verkauf',
    'abgang_schlachtung': 'Abgang Schlachtung',
    'abgang_verendung': 'Abgang Verendung',
    'abgang_sonstig': 'Abgang Sonstig',
    'umstallung': 'Umstallung intern',
}

VERABREICHUNGSARTEN_RIND = [
    'Injektion subkutan',
    'Injektion intramuskulär',
    'Injektion intravenös',
    'Injektion intramammär',
    'Oral / Drench',
    'Futter',
    'Wasser',
    'Intrauterin',
    'Topisch',
    'Sonstige',
]

LAKTATION_STATUS = [
    'laktierend',
    'trocken',
    'färse',
    'galt',
]

IMPF_KRANKHEITEN_RIND = [
    'BVD (Bovines Virusdiarrhoe)',
    'IBR/IPV (Infektiöse Bovine Rhinotracheitis)',
    'BRD (Bovine Respiratory Disease)',
    'Leptospirose',
    'Clostridien',
    'Rotavirus / Coronavirus (Kälberdurchfall)',
    'Salmonellose',
    'Listeriose',
    'Maul- und Klauenseuche (MKS)',
    'Lumpy Skin Disease (LSD)',
    'Sonstige',
]

ABGANGSURSACHEN = [
    'Eutererkrankung',
    'Fruchtbarkeitsprobleme',
    'Klauen-/Gliedmaßenprobleme',
    'Stoffwechselstörung',
    'Verletzung',
    'Alter',
    'Schlechte Leistung',
    'Sonstige',
]


class Rind(db.Model):
    """
    Tierstammdaten – Bestandsregister.

    Pflichtfelder laut österreichischem Rinderkennzeichnungsrecht
    (AMA/VIS Meldung innerhalb 7 Tage nach Zugang/Geburt).
    """
    __tablename__ = 'rind'

    id = db.Column(db.Integer, primary_key=True)

    # Ohrmarke (gesetzlich verpflichtend, AT: ATS-123456789012)
    ohrmarke = db.Column(db.String(20), nullable=False, unique=True, index=True)
    ohrmarke_2 = db.Column(db.String(20))  # Ersatzohrmarke

    # Stammdaten
    name = db.Column(db.String(100))  # Hofname / Stallname
    rasse = db.Column(db.String(100))
    geschlecht = db.Column(db.String(1), default='W')  # M / W
    geburtsdatum = db.Column(db.Date)
    geburtsgewicht_kg = db.Column(db.Numeric(6, 1))

    # Abstammung
    mutter_ohrmarke = db.Column(db.String(20))
    vater_hb_nr = db.Column(db.String(50))  # Herdbuchnummer / Besamungsstiernummer

    # Herkunft (bei Zukauf)
    herkunft_betrieb = db.Column(db.String(200))
    herkunft_land = db.Column(db.String(2))  # ISO 3166-1 alpha-2
    eingang_datum = db.Column(db.Date)

    # Status
    status = db.Column(db.String(20), default='aktiv')  # aktiv, abgegangen, verendet, geschlachtet
    nutzungsart = db.Column(db.String(20), default='Milch')
    abgang_datum = db.Column(db.Date)
    abgangsursache = db.Column(db.String(100))

    # AMA-Meldung
    ama_gemeldet = db.Column(db.Boolean, default=False)
    ama_meldedatum = db.Column(db.Date)

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tierbewegungen = db.relationship('Tierbewegung', back_populates='rind',
                                     lazy='dynamic', cascade='all, delete-orphan')
    arzneimittel_anwendungen = db.relationship('RindArzneimittelAnwendung', back_populates='rind',
                                               lazy='dynamic', cascade='all, delete-orphan')
    impfungen = db.relationship('RindImpfung', back_populates='rind',
                                lazy='dynamic', cascade='all, delete-orphan')
    laktationen = db.relationship('Laktation', back_populates='rind',
                                  lazy='dynamic', cascade='all, delete-orphan')
    besamungen = db.relationship('Besamung', back_populates='rind',
                                 lazy='dynamic', cascade='all, delete-orphan')
    mlp_pruefungen = db.relationship('MLPPruefung', back_populates='rind',
                                     lazy='dynamic', cascade='all, delete-orphan')
    euter_befunde = db.relationship('EuterGesundheit', back_populates='rind',
                                    lazy='dynamic', cascade='all, delete-orphan')
    klauen_befunde = db.relationship('KlauenpflegeBefund', back_populates='rind',
                                     lazy='dynamic', cascade='all, delete-orphan')

    @property
    def alter_monate(self):
        if not self.geburtsdatum:
            return None
        delta = date.today() - self.geburtsdatum
        return delta.days // 30

    @property
    def alter_jahre(self):
        if not self.geburtsdatum:
            return None
        today = date.today()
        years = today.year - self.geburtsdatum.year
        if (today.month, today.day) < (self.geburtsdatum.month, self.geburtsdatum.day):
            years -= 1
        return years

    @property
    def ist_aktiv(self):
        return self.status == 'aktiv'

    @property
    def hat_aktive_wartezeit(self):
        """Prüft ob eine TAMG-Wartezeit (Milch oder Fleisch) aktiv ist."""
        heute = date.today()
        return self.arzneimittel_anwendungen.filter(
            db.or_(
                RindArzneimittelAnwendung.wartezeit_milch_ende >= heute,
                RindArzneimittelAnwendung.wartezeit_fleisch_ende >= heute,
            )
        ).count() > 0

    @property
    def aktuelle_laktation(self):
        return self.laktationen.filter_by(ist_aktiv=True).first()

    @property
    def ama_meldung_faellig(self):
        """Prüft ob die AMA-Meldung noch aussteht (Frist 7 Tage)."""
        if self.ama_gemeldet:
            return False
        ref_datum = self.eingang_datum or self.geburtsdatum
        if not ref_datum:
            return False
        return (date.today() - ref_datum).days >= 7

    def __repr__(self):
        return f'<Rind {self.ohrmarke} {self.name or ""}>'


class Tierbewegung(db.Model):
    """
    Tierbewegungsregister – gesetzlich vorgeschrieben.

    Alle Zu- und Abgänge müssen binnen 7 Tagen an die AMA (AT)
    bzw. HIT-Datenbank (DE) gemeldet werden.
    """
    __tablename__ = 'tierbewegung'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    typ = db.Column(db.String(30), nullable=False)  # aus TIERBEWEGUNG_TYPEN

    # Herkunft / Ziel
    gegenpartei_betrieb = db.Column(db.String(200))  # Verkäufer oder Käufer
    gegenpartei_land = db.Column(db.String(2))
    schlachthof = db.Column(db.String(200))
    gewicht_kg = db.Column(db.Numeric(6, 1))
    preis = db.Column(db.Numeric(10, 2))

    # Meldung
    ama_gemeldet = db.Column(db.Boolean, default=False)
    ama_meldedatum = db.Column(db.Date)
    beleg_nr = db.Column(db.String(50))

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    rind = db.relationship('Rind', back_populates='tierbewegungen')

    @property
    def typ_name(self):
        return TIERBEWEGUNG_TYPEN.get(self.typ, self.typ)

    @property
    def meldung_faellig(self):
        if self.ama_gemeldet:
            return False
        return (date.today() - self.datum).days >= 7

    def __repr__(self):
        return f'<Tierbewegung {self.datum} {self.typ} Rind={self.rind_id}>'


class Laktation(db.Model):
    """
    Laktationserfassung – pro Kuh pro Laktationsperiode.

    Laktationsnummer, Kalbedatum, Trockenstell- und Abkalbedaten.
    """
    __tablename__ = 'laktation'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)

    laktationsnummer = db.Column(db.Integer)
    kalbedatum = db.Column(db.Date)
    kalbeverlauf = db.Column(db.String(50))  # normal, schwer, Kaiserschnitt, Totgeburt
    kalb_ohrmarke = db.Column(db.String(20))
    kalb_geschlecht = db.Column(db.String(1))

    # Laktationsverlauf
    status = db.Column(db.String(20), default='laktierend')  # laktierend, trocken, galt
    trockenstell_datum = db.Column(db.Date)
    laktations_ende = db.Column(db.Date)
    ist_aktiv = db.Column(db.Boolean, default=True)

    # 305-Tage-Leistung (wird manuell oder aus Kontrollmilchprüfung eingetragen)
    milch_305_tage_kg = db.Column(db.Numeric(8, 2))
    fett_prozent = db.Column(db.Numeric(4, 2))
    eiweiss_prozent = db.Column(db.Numeric(4, 2))
    zellzahl_tsd = db.Column(db.Integer)  # somatische Zellzahl in Tausend/ml

    # Transitphase / Peripartal
    body_condition_score_trocken = db.Column(db.Numeric(3, 2))   # BCS beim Trockenstellen (Ziel: 3,5)
    body_condition_score_kalbung = db.Column(db.Numeric(3, 2))   # BCS bei Kalbung (Ziel: 3,0–3,5)
    body_condition_score_100d = db.Column(db.Numeric(3, 2))      # BCS 100 Tage p.p.
    ketose_test_datum = db.Column(db.Date)
    ketose_ergebnis = db.Column(db.String(20))   # negativ, subklinisch, klinisch
    milchfieber = db.Column(db.Boolean, default=False)
    labmagen = db.Column(db.Boolean, default=False)

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    rind = db.relationship('Rind', back_populates='laktationen')
    besamungen = db.relationship('Besamung', back_populates='laktation',
                                 lazy='dynamic', cascade='all, delete-orphan')
    mlp_pruefungen = db.relationship('MLPPruefung', back_populates='laktation',
                                     lazy='dynamic', cascade='all, delete-orphan')

    @property
    def laktationstage(self):
        if not self.kalbedatum:
            return None
        ende = self.laktations_ende or date.today()
        return (ende - self.kalbedatum).days

    @property
    def trockenstehzeit_tage(self):
        """Tage zwischen Trockenstellen und Kalbung (rückblickend)."""
        if self.trockenstell_datum and self.kalbedatum:
            return (self.kalbedatum - self.trockenstell_datum).days
        return None

    @property
    def tragende_besamung(self):
        """Die Besamung die zur Trächtigkeit geführt hat."""
        return self.besamungen.filter_by(traechtig=True).order_by(
            Besamung.datum.asc()).first()

    @property
    def guestzeit_tage(self):
        """Tage von Kalbung bis zur tragenden Besamung."""
        bs = self.tragende_besamung
        if self.kalbedatum and bs:
            return (bs.datum - self.kalbedatum).days
        return None

    @property
    def zwischenkalbezeit_tage(self):
        """ZKZ: von dieser Kalbung bis zur nächsten (falls bekannt)."""
        if not self.kalbedatum:
            return None
        bs = self.tragende_besamung
        if bs and bs.errechneter_kalbetermin:
            return (bs.errechneter_kalbetermin - self.kalbedatum).days
        return None

    def __repr__(self):
        return f'<Laktation Rind={self.rind_id} Lakt={self.laktationsnummer}>'


class RindArzneimittelAnwendung(db.Model):
    """
    TAMG-Behandlungsjournal für Rinder.

    Gesetzlich vorgeschriebene Dokumentation gemäß
    Tierarzneimittelgesetz (TAMG AT) / TÄHAV (DE).
    Wartezeiten für Milch UND Fleisch werden separat berechnet.
    """
    __tablename__ = 'rind_arzneimittel_anwendung'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)

    # Behandlungsdaten (TAMG-Pflichtfelder)
    beginn = db.Column(db.Date, nullable=False)
    ende = db.Column(db.Date)
    arzneimittel_name = db.Column(db.String(200), nullable=False)
    wirkstoff = db.Column(db.String(200))
    zulassungsnummer = db.Column(db.String(50))
    charge = db.Column(db.String(100))
    dosierung = db.Column(db.String(200))
    verabreichungsart = db.Column(db.String(50))
    behandlungsdauer_tage = db.Column(db.Integer)
    anzahl_tiere = db.Column(db.Integer, default=1)

    # Diagnose / Verschreibung
    diagnose = db.Column(db.String(200))
    tierarzt_name = db.Column(db.String(200))
    rezept_nr = db.Column(db.String(50))
    ist_antibiotikum = db.Column(db.Boolean, default=False)

    # Wartezeiten (Pflichtfeld TAMG)
    wartezeit_milch_tage = db.Column(db.Integer, default=0)
    wartezeit_milch_ende = db.Column(db.Date)
    wartezeit_fleisch_tage = db.Column(db.Integer, default=0)
    wartezeit_fleisch_ende = db.Column(db.Date)

    beleg_nr = db.Column(db.String(50))
    bemerkung = db.Column(db.Text)

    # Tierarzt-Signatur
    signatur_data = db.Column(db.Text)         # Base64-PNG
    signatur_datum = db.Column(db.DateTime)
    signatur_name = db.Column(db.String(200))

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    rind = db.relationship('Rind', back_populates='arzneimittel_anwendungen')

    def berechne_wartezeiten(self):
        """Wartezeit-Enden aus Behandlungsende + Wartezeit-Tage berechnen."""
        ref = self.ende or self.beginn
        if ref:
            if self.wartezeit_milch_tage:
                self.wartezeit_milch_ende = ref + timedelta(days=self.wartezeit_milch_tage)
            if self.wartezeit_fleisch_tage:
                self.wartezeit_fleisch_ende = ref + timedelta(days=self.wartezeit_fleisch_tage)

    @property
    def wartezeit_milch_aktiv(self):
        if self.wartezeit_milch_ende:
            return self.wartezeit_milch_ende >= date.today()
        return False

    @property
    def wartezeit_fleisch_aktiv(self):
        if self.wartezeit_fleisch_ende:
            return self.wartezeit_fleisch_ende >= date.today()
        return False

    @property
    def wartezeit_milch_resttage(self):
        if self.wartezeit_milch_ende and self.wartezeit_milch_aktiv:
            return (self.wartezeit_milch_ende - date.today()).days
        return 0

    @property
    def wartezeit_fleisch_resttage(self):
        if self.wartezeit_fleisch_ende and self.wartezeit_fleisch_aktiv:
            return (self.wartezeit_fleisch_ende - date.today()).days
        return 0

    def __repr__(self):
        return f'<RindArzneimittelAnwendung {self.arzneimittel_name} Rind={self.rind_id}>'


class RindImpfung(db.Model):
    """Impfungs-Dokumentation für Rinder."""
    __tablename__ = 'rind_impfung'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    impfstoff = db.Column(db.String(200))
    krankheit = db.Column(db.String(100))
    charge = db.Column(db.String(100))
    verabreichungsart = db.Column(db.String(50))
    tierarzt = db.Column(db.String(200))
    naechste_impfung = db.Column(db.Date)

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    rind = db.relationship('Rind', back_populates='impfungen')

    def __repr__(self):
        return f'<RindImpfung {self.datum} {self.krankheit} Rind={self.rind_id}>'


# ═══════════════════════════════════════════════════════════════
# Phase 2 – Modelle
# ═══════════════════════════════════════════════════════════════

# Konstanten Phase 2
BESAMUNG_ART = ['Künstliche Besamung (KB)', 'Natursprung']
KALBEVERLAUF_ARTEN = ['normal', 'leicht erschwert', 'schwer (Geburtshilfe)', 'Kaiserschnitt', 'Totgeburt']
SCHALMTEST_ERGEBNISSE = ['negativ', '(+)', '+', '++', '+++']
MASTITIS_TYPEN = ['klinisch', 'subklinisch']
MASTITIS_ERREGER = [
    'Staphylococcus aureus',
    'Streptococcus uberis',
    'Streptococcus agalactiae',
    'Streptococcus dysgalactiae',
    'Escherichia coli',
    'Klebsiella spp.',
    'Enterococcus spp.',
    'Trueperella pyogenes',
    'Koagulase-negative Staphylokokken (KNS)',
    'Sonstige',
    'Kein Erreger nachgewiesen',
]
EUTERVIERTEL = ['VL', 'VR', 'HL', 'HR', 'gesamt']
KLAUEN_BEFUNDE = [
    'IK (Interdigitale Phlegmone)',
    'DF (Dermatitis digitalis / Mortellaro)',
    'BS (Ballensohlengeschwür)',
    'DS (Doppelsohle)',
    'WLD (White Line Disease)',
    'LW (Limax)',
    'KW (Klauenbedeckung)',
    'SW (Sohlengeschwür)',
    'Sonstiges',
]
LAMENESS_GRAD = {1: 'Keine Lahmheit', 2: 'Geringgradig', 3: 'Mittelgradig', 4: 'Hochgradig'}


class Besamung(db.Model):
    """
    Besamungsprotokoll – einzelner Besamungsvorgang.

    Jede Kuh kann pro Laktationsperiode mehrere Besamungen haben,
    bis eine Trächtigkeit bestätigt ist.
    """
    __tablename__ = 'besamung'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)
    laktation_id = db.Column(db.Integer, db.ForeignKey('laktation.id', ondelete='SET NULL'))

    datum = db.Column(db.Date, nullable=False)
    art = db.Column(db.String(30), default='Künstliche Besamung (KB)')  # KB / Natursprung
    stier_name = db.Column(db.String(100))         # Stiername oder Herdbuchnummer
    stier_hb_nr = db.Column(db.String(50))         # Besamungsbullennummer (ZAR/RDV)
    portion_nr = db.Column(db.String(50))          # Samenportionsnummer (Rückverfolgung)
    besamungstechniker = db.Column(db.String(100))

    # Trächtigkeitskontrolle
    td_datum = db.Column(db.Date)                  # Datum Trächtigkeitsdiagnose
    traechtig = db.Column(db.Boolean)              # None = noch nicht untersucht
    td_methode = db.Column(db.String(50))          # Ultraschall / Rektalpalpation / Bluttest
    tierarzt_td = db.Column(db.String(100))

    # Berechnungen
    errechneter_kalbetermin = db.Column(db.Date)   # wird automatisch berechnet

    bemerkung = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    rind = db.relationship('Rind', back_populates='besamungen')
    laktation = db.relationship('Laktation', back_populates='besamungen')

    def berechne_kalbetermin(self, rasse=None):
        """283 Tage (Holstein) / 285 Tage (Fleckvieh) ab Besamungsdatum."""
        if self.datum:
            tage = 285 if rasse and 'Fleckvieh' in rasse else 283
            self.errechneter_kalbetermin = self.datum + timedelta(days=tage)

    @property
    def rastzeit_tage(self):
        """Tage von Kalbung bis zu dieser Besamung."""
        if self.laktation and self.laktation.kalbedatum and self.datum:
            return (self.datum - self.laktation.kalbedatum).days
        return None

    def __repr__(self):
        return f'<Besamung {self.datum} Rind={self.rind_id}>'


class MLPPruefung(db.Model):
    """
    Monatliche Milchleistungsprüfung (MLP / Kontrollmilchprüfung).

    Erfasst die tierindividuellen LKV-Prüfungsergebnisse.
    Rechtsgrundlage: EU-VO 2016/1012 (Tierzucht-VO), LKV Austria.
    """
    __tablename__ = 'mlp_pruefung'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)
    laktation_id = db.Column(db.Integer, db.ForeignKey('laktation.id', ondelete='SET NULL'))

    datum = db.Column(db.Date, nullable=False)
    laktationstag = db.Column(db.Integer)          # Tag seit letzter Kalbung (auto)

    # Kernwerte (LKV-Prüfung)
    milchmenge_kg = db.Column(db.Numeric(6, 2))    # Tagesgemelk kg
    fett_prozent = db.Column(db.Numeric(4, 2))
    eiweiss_prozent = db.Column(db.Numeric(4, 2))
    laktose_prozent = db.Column(db.Numeric(4, 2))
    harnstoff_mg_dl = db.Column(db.Integer)        # mg/l; Richtwert 150–300

    # Zellzahl (SCC – Somatic Cell Count)
    zellzahl_tsd = db.Column(db.Integer)           # Tausend/ml; Alarm > 200 (subkl.) / > 400 (klin.)

    # Berechnungen (werden automatisch befüllt)
    ecm_kg = db.Column(db.Numeric(6, 2))           # Energiekorrigierte Milch
    fett_eiweiss_quotient = db.Column(db.Numeric(4, 3))  # < 1,0 = Azidose-Risiko

    # Kontrolldaten
    pruefer = db.Column(db.String(100))            # LKV-Prüfer
    probenahme_morgen_kg = db.Column(db.Numeric(5, 2))
    probenahme_abend_kg = db.Column(db.Numeric(5, 2))

    bemerkung = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    rind = db.relationship('Rind', back_populates='mlp_pruefungen')
    laktation = db.relationship('Laktation', back_populates='mlp_pruefungen')

    def berechne_kennzahlen(self):
        """ECM und F:E-Quotient aus Rohdaten berechnen."""
        if self.milchmenge_kg and self.fett_prozent and self.eiweiss_prozent:
            m = float(self.milchmenge_kg)
            f = float(self.fett_prozent)
            e = float(self.eiweiss_prozent)
            # ECM-Formel (Sjaunja et al.)
            ecm = m * (0.383 * f + 0.242 * e + 0.7832) / 3.1138
            self.ecm_kg = round(ecm, 2)
        if self.fett_prozent and self.eiweiss_prozent and float(self.eiweiss_prozent) > 0:
            self.fett_eiweiss_quotient = round(
                float(self.fett_prozent) / float(self.eiweiss_prozent), 3)

    @property
    def zellzahl_status(self):
        """Ampel-Bewertung der Zellzahl."""
        if not self.zellzahl_tsd:
            return None
        if self.zellzahl_tsd < 100:
            return 'ok'       # gesund
        if self.zellzahl_tsd < 200:
            return 'warn'     # erhöht, beobachten
        if self.zellzahl_tsd < 400:
            return 'danger'   # subklinische Mastitis
        return 'critical'     # klinische Mastitis, EU-Ablieferungsgrenze

    @property
    def harnstoff_status(self):
        """Harnstoff-Bewertung als Fütterungsindikator."""
        if not self.harnstoff_mg_dl:
            return None
        if self.harnstoff_mg_dl < 100:
            return 'low'      # Energiemangel + Eiweißmangel
        if self.harnstoff_mg_dl < 150:
            return 'warn_low' # leichter Eiweißmangel
        if self.harnstoff_mg_dl <= 300:
            return 'ok'       # optimal
        return 'high'         # Eiweißüberschuss → Fruchtbarkeitsprobleme

    def __repr__(self):
        return f'<MLPPruefung {self.datum} Rind={self.rind_id}>'


class EuterGesundheit(db.Model):
    """
    Eutergesundheits-Befund – Schalmtest, Mastitis-Dokumentation.

    Verbindung zum TAMG-Journal über behandlung_id.
    """
    __tablename__ = 'euter_gesundheit'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    euterviertel = db.Column(db.String(10))        # VL, VR, HL, HR, gesamt

    # Schalmtest
    schalmtest = db.Column(db.String(10))          # negativ, (+), +, ++, +++

    # Labordiagnose
    zellzahl_tsd = db.Column(db.Integer)           # Einzeltier-Zellzahl
    erreger = db.Column(db.String(100))
    mastitis_typ = db.Column(db.String(20))        # klinisch / subklinisch

    # Behandlung
    behandlung_id = db.Column(db.Integer,
                               db.ForeignKey('rind_arzneimittel_anwendung.id', ondelete='SET NULL'))
    tierarzt = db.Column(db.String(100))

    bemerkung = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    rind = db.relationship('Rind', back_populates='euter_befunde')
    behandlung = db.relationship('RindArzneimittelAnwendung')

    def __repr__(self):
        return f'<EuterGesundheit {self.datum} {self.euterviertel} Rind={self.rind_id}>'


class KlauenpflegeBefund(db.Model):
    """Klauenpflege- und Klauengesundheits-Protokoll."""
    __tablename__ = 'klauenpflege_befund'

    id = db.Column(db.Integer, primary_key=True)
    rind_id = db.Column(db.Integer, db.ForeignKey('rind.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    klauenpfleger = db.Column(db.String(100))
    befund = db.Column(db.String(100))             # aus KLAUEN_BEFUNDE
    schweregrad = db.Column(db.Integer)            # 1–4 (International Lameness Scoring)
    behandelt = db.Column(db.Boolean, default=False)
    behandlung_id = db.Column(db.Integer,
                               db.ForeignKey('rind_arzneimittel_anwendung.id', ondelete='SET NULL'))
    naechste_pflege = db.Column(db.Date)

    bemerkung = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    rind = db.relationship('Rind', back_populates='klauen_befunde')
    behandlung = db.relationship('RindArzneimittelAnwendung')

    @property
    def schweregrad_name(self):
        return LAMENESS_GRAD.get(self.schweregrad, '–')

    def __repr__(self):
        return f'<KlauenpflegeBefund {self.datum} {self.befund} Rind={self.rind_id}>'


class WeidePeriode(db.Model):
    """
    Weidebuch – Dokumentation für ÖPUL-Nachweis.

    ÖPUL 2023 "Weidehaltung Rinder": mind. 120 Weidetage,
    mind. 4 Stunden/Tag. Bei Kontrolle durch AMA prüfpflichtig.
    """
    __tablename__ = 'weide_periode'

    id = db.Column(db.Integer, primary_key=True)

    datum_von = db.Column(db.Date, nullable=False)
    datum_bis = db.Column(db.Date)
    weide_bezeichnung = db.Column(db.String(200))  # Schlagname / INVEKOS-Nr.
    weide_flaeche_ha = db.Column(db.Numeric(8, 2))
    anzahl_tiere = db.Column(db.Integer)
    tier_gruppe = db.Column(db.String(100))        # Kühe, Kalbinnen, Kälber etc.
    stunden_pro_tag = db.Column(db.Numeric(3, 1))  # Mindestanforderung ÖPUL: 4h

    bemerkung = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def weidetage(self):
        if self.datum_von and self.datum_bis:
            return (self.datum_bis - self.datum_von).days + 1
        if self.datum_von:
            return (date.today() - self.datum_von).days + 1
        return None

    @property
    def oepul_konform(self):
        """Prüft ob ÖPUL-Mindestanforderungen erfüllt (4h/Tag)."""
        return self.stunden_pro_tag is not None and float(self.stunden_pro_tag) >= 4.0

    def __repr__(self):
        return f'<WeidePeriode {self.datum_von} – {self.datum_bis}>'


class TankmilchAuswertung(db.Model):
    """
    Monatliche Tankmilch-Qualitätsauswertung (Molkerei-Abrechnung).

    Gesetzliche Grenzwerte (EU-VO 853/2004):
    - Keimzahl: < 100.000/ml (Liefersperre ab 3 Monate Überschreitung)
    - Zellzahl: < 400.000/ml
    """
    __tablename__ = 'tankmilch_auswertung'

    id = db.Column(db.Integer, primary_key=True)

    jahr = db.Column(db.Integer, nullable=False)
    monat = db.Column(db.Integer, nullable=False)  # 1–12
    milchmenge_kg = db.Column(db.Numeric(10, 2))

    # Qualitätsparameter
    fett_prozent = db.Column(db.Numeric(4, 2))
    eiweiss_prozent = db.Column(db.Numeric(4, 2))
    gesamtkeimzahl = db.Column(db.Integer)         # /ml; Grenzwert: 100.000
    zellzahl_tank = db.Column(db.Integer)          # /ml; Grenzwert: 400.000
    gefrierpunkt = db.Column(db.Numeric(5, 3))     # °C; ≤ -0,520 (Wasserverfälschung)
    hemmstoff = db.Column(db.Boolean)              # True = Hemmstoff positiv (Antibiotika!)

    # Abrechnung
    auszahlungspreis_ct_kg = db.Column(db.Numeric(6, 3))
    qualitaetszuschlag_ct = db.Column(db.Numeric(5, 3))
    molkerei = db.Column(db.String(100))

    bemerkung = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def keimzahl_ok(self):
        return self.gesamtkeimzahl is None or self.gesamtkeimzahl < 100000

    @property
    def zellzahl_ok(self):
        return self.zellzahl_tank is None or self.zellzahl_tank < 400000

    @property
    def monat_name(self):
        monate = ['Jan', 'Feb', 'Mär', 'Apr', 'Mai', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dez']
        return monate[self.monat - 1] if 1 <= self.monat <= 12 else str(self.monat)

    def __repr__(self):
        return f'<TankmilchAuswertung {self.jahr}/{self.monat:02d}>'
