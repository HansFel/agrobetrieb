"""
Milchvieh-Modul – Datenmodelle (Phase 1).

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

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    rind = db.relationship('Rind', back_populates='laktationen')

    @property
    def laktationstage(self):
        if not self.kalbedatum:
            return None
        ende = self.laktations_ende or date.today()
        return (ende - self.kalbedatum).days

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
