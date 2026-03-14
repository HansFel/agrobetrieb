"""
Legehennen Pro-Modul – Datenmodelle.

Herdenmanagement für Legehennenhalter inkl. Stallbuch,
Tagesleistung, Sortierergebnisse, Tierarzt, Impfungen,
Medikamente, Salmonellen-Monitoring und Ereignisse.
"""
from datetime import datetime, date, timedelta
from app.extensions import db


# Konstanten
HALTUNGSFORMEN = {
    0: 'Bio',
    1: 'Freiland',
    2: 'Bodenhaltung',
    3: 'Kleingruppe',
}

MEDIKAMENT_TYPEN = [
    'Antibiotikum',
    'Antiparasitikum',
    'Vitamine',
    'Impfstoff',
    'Sonstiges',
]

VERABREICHUNGSARTEN = [
    'Trinkwasser',
    'Futter',
    'Injektion',
    'Spray',
    'Augentropfen',
    'Flügelstichmethode',
]

IMPF_KRANKHEITEN = [
    'Newcastle Disease (ND)',
    'Infektiöse Bronchitis (IB)',
    'Marek-Krankheit',
    'Gumboro (IBD)',
    'Egg Drop Syndrome (EDS)',
    'Aviäre Enzephalomyelitis (AE)',
    'Salmonellen (SE)',
    'Kokzidiose',
    'Mykoplasmen (MG)',
    'Pocken',
    'Sonstige',
]

PROBENARTEN = [
    'Sockentupfer',
    'Kotprobe',
    'Staubprobe',
    'Eierprobe',
    'Sonstige',
]

EREIGNIS_KATEGORIEN = [
    'Desinfektion',
    'Entwesung',
    'Stromausfall',
    'Stallpflicht',
    'Behördenkontrolle',
    'Futterwechsel',
    'Lichtwechsel',
    'Einstallung',
    'Ausstallung',
    'Sonstiges',
]


class Herde(db.Model):
    """Legehennen-Herde (ein Durchgang)."""
    __tablename__ = 'herde'

    id = db.Column(db.Integer, primary_key=True)

    # Stammdaten
    name = db.Column(db.String(100), nullable=False)
    rasse = db.Column(db.String(100))
    haltungsform = db.Column(db.Integer, default=2)  # 0=Bio, 1=Freiland, 2=Boden, 3=Kleingruppe
    schlupfdatum = db.Column(db.Date)
    lieferdatum = db.Column(db.Date)
    lieferant = db.Column(db.String(200))
    lieferant_vvvo = db.Column(db.String(50))
    anfangsbestand = db.Column(db.Integer, nullable=False)
    aktueller_bestand = db.Column(db.Integer)

    # Stall
    stall_nr = db.Column(db.String(50))
    stall_flaeche_m2 = db.Column(db.Numeric(10, 2))
    auslauf_flaeche_m2 = db.Column(db.Numeric(10, 2))
    nest_plaetze = db.Column(db.Integer)

    # Eierkennzeichnung
    erzeuger_code = db.Column(db.String(20))

    # Legeperiode
    legebeginn = db.Column(db.Date)
    erwartetes_ende = db.Column(db.Date)
    ausstalldatum = db.Column(db.Date)
    ist_aktiv = db.Column(db.Boolean, default=True)

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    tagesleistungen = db.relationship('Tagesleistung', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')
    sortierergebnisse = db.relationship('Sortierergebnis', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')
    tierarzt_besuche = db.relationship('TierarztBesuch', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')
    impfungen = db.relationship('Impfung', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')
    medikament_behandlungen = db.relationship('MedikamentBehandlung', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')
    futter_lieferungen = db.relationship('FutterLieferung', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')
    salmonellen_proben = db.relationship('SalmonellenProbe', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')
    ereignisse = db.relationship('HerdeEreignis', back_populates='herde', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def haltungsform_name(self):
        return HALTUNGSFORMEN.get(self.haltungsform, 'Unbekannt')

    @property
    def alter_wochen(self):
        """Alter in Lebenswochen seit Schlupf."""
        if not self.schlupfdatum:
            return None
        delta = date.today() - self.schlupfdatum
        return delta.days // 7

    @property
    def alter_tage(self):
        """Alter in Lebenstagen seit Schlupf."""
        if not self.schlupfdatum:
            return None
        return (date.today() - self.schlupfdatum).days

    @property
    def mortalitaet_prozent(self):
        """Kumulierte Mortalität in %."""
        if not self.anfangsbestand or not self.aktueller_bestand:
            return 0
        return round((self.anfangsbestand - self.aktueller_bestand) / self.anfangsbestand * 100, 2)

    @property
    def hat_aktive_wartezeit(self):
        """Prüft ob eine Medikamenten-Wartezeit aktiv ist."""
        heute = date.today()
        return self.medikament_behandlungen.filter(
            MedikamentBehandlung.wartezeit_ende >= heute
        ).count() > 0

    @property
    def naechste_impfung(self):
        """Nächste fällige Impfung."""
        heute = date.today()
        return self.impfungen.filter(
            Impfung.naechste_impfung >= heute
        ).order_by(Impfung.naechste_impfung.asc()).first()

    def __repr__(self):
        return f'<Herde {self.name}>'


class Tagesleistung(db.Model):
    """Tägliche Produktion – Stallbuch-Eintrag."""
    __tablename__ = 'tagesleistung'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)

    # Eierproduktion
    eier_gesamt = db.Column(db.Integer, default=0)
    eier_verkaufsfaehig = db.Column(db.Integer, default=0)
    eier_knick = db.Column(db.Integer, default=0)
    eier_bruch = db.Column(db.Integer, default=0)
    eier_schmutzig = db.Column(db.Integer, default=0)
    eier_wind = db.Column(db.Integer, default=0)
    eier_boden = db.Column(db.Integer, default=0)
    eigewicht_durchschnitt = db.Column(db.Numeric(5, 2))

    # Bestand
    tierbestand = db.Column(db.Integer)
    verluste = db.Column(db.Integer, default=0)
    verlust_ursache = db.Column(db.String(200))

    # Verbrauch
    futterverbrauch_kg = db.Column(db.Numeric(8, 2))
    wasserverbrauch_l = db.Column(db.Numeric(8, 2))

    # Klima
    temperatur_stall = db.Column(db.Numeric(4, 1))
    luftfeuchtigkeit = db.Column(db.Numeric(4, 1))
    lichtprogramm_std = db.Column(db.Numeric(4, 1))

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    herde = db.relationship('Herde', back_populates='tagesleistungen')

    @property
    def lebenstag(self):
        if self.herde and self.herde.schlupfdatum:
            return (self.datum - self.herde.schlupfdatum).days
        return None

    @property
    def lebenswoche(self):
        lt = self.lebenstag
        return lt // 7 if lt is not None else None

    @property
    def legerate_prozent(self):
        if self.eier_gesamt and self.tierbestand and self.tierbestand > 0:
            return round(self.eier_gesamt / self.tierbestand * 100, 2)
        return 0

    @property
    def futter_pro_tier_g(self):
        if self.futterverbrauch_kg and self.tierbestand and self.tierbestand > 0:
            return round(float(self.futterverbrauch_kg) * 1000 / self.tierbestand, 1)
        return None

    @property
    def futter_pro_ei_g(self):
        if self.futterverbrauch_kg and self.eier_gesamt and self.eier_gesamt > 0:
            return round(float(self.futterverbrauch_kg) * 1000 / self.eier_gesamt, 1)
        return None

    def __repr__(self):
        return f'<Tagesleistung {self.datum} Herde={self.herde_id}>'


class Sortierergebnis(db.Model):
    """Packstellen-Sortierung nach Eigröße."""
    __tablename__ = 'sortierergebnis'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    eier_gesamt = db.Column(db.Integer, default=0)
    groesse_s = db.Column(db.Integer, default=0)   # < 53g
    groesse_m = db.Column(db.Integer, default=0)   # 53-63g
    groesse_l = db.Column(db.Integer, default=0)   # 63-73g
    groesse_xl = db.Column(db.Integer, default=0)  # > 73g
    aussortiert = db.Column(db.Integer, default=0)

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    herde = db.relationship('Herde', back_populates='sortierergebnisse')

    @property
    def anteil_s(self):
        if self.eier_gesamt and self.eier_gesamt > 0:
            return round(self.groesse_s / self.eier_gesamt * 100, 1)
        return 0

    @property
    def anteil_m(self):
        if self.eier_gesamt and self.eier_gesamt > 0:
            return round(self.groesse_m / self.eier_gesamt * 100, 1)
        return 0

    @property
    def anteil_l(self):
        if self.eier_gesamt and self.eier_gesamt > 0:
            return round(self.groesse_l / self.eier_gesamt * 100, 1)
        return 0

    @property
    def anteil_xl(self):
        if self.eier_gesamt and self.eier_gesamt > 0:
            return round(self.groesse_xl / self.eier_gesamt * 100, 1)
        return 0

    def __repr__(self):
        return f'<Sortierergebnis {self.datum} Herde={self.herde_id}>'


class TierarztBesuch(db.Model):
    """Tierarztbesuch-Dokumentation."""
    __tablename__ = 'tierarzt_besuch'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    tierarzt_name = db.Column(db.String(200))
    tierarzt_praxis = db.Column(db.String(200))
    grund = db.Column(db.String(200))
    diagnose = db.Column(db.Text)
    massnahmen = db.Column(db.Text)
    naechster_besuch = db.Column(db.Date)
    kosten = db.Column(db.Numeric(10, 2))

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    herde = db.relationship('Herde', back_populates='tierarzt_besuche')

    def __repr__(self):
        return f'<TierarztBesuch {self.datum} Herde={self.herde_id}>'


class Impfung(db.Model):
    """Impfung-Dokumentation."""
    __tablename__ = 'impfung'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'), nullable=False)

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
    herde = db.relationship('Herde', back_populates='impfungen')

    def __repr__(self):
        return f'<Impfung {self.datum} {self.krankheit} Herde={self.herde_id}>'


class MedikamentBehandlung(db.Model):
    """Tierarzneimittel-Dokumentation gemäß TAMG."""
    __tablename__ = 'medikament_behandlung'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'), nullable=False)

    beginn = db.Column(db.Date, nullable=False)
    ende = db.Column(db.Date)
    medikament_name = db.Column(db.String(200), nullable=False)
    wirkstoff = db.Column(db.String(200))
    typ = db.Column(db.String(50))  # Antibiotikum, Antiparasitikum, Vitamine, Sonstiges
    charge = db.Column(db.String(100))
    dosierung = db.Column(db.String(100))
    verabreichungsart = db.Column(db.String(50))
    diagnose = db.Column(db.String(200))
    tierarzt = db.Column(db.String(200))
    anzahl_tiere = db.Column(db.Integer)
    wartezeit_tage = db.Column(db.Integer, default=0)
    wartezeit_ende = db.Column(db.Date)
    ist_antibiotikum = db.Column(db.Boolean, default=False)
    beleg_nr = db.Column(db.String(50))

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    herde = db.relationship('Herde', back_populates='medikament_behandlungen')

    def berechne_wartezeit_ende(self):
        """Wartezeit-Ende automatisch berechnen."""
        if self.ende and self.wartezeit_tage:
            self.wartezeit_ende = self.ende + timedelta(days=self.wartezeit_tage)

    @property
    def wartezeit_aktiv(self):
        if self.wartezeit_ende:
            return self.wartezeit_ende >= date.today()
        return False

    @property
    def wartezeit_resttage(self):
        if self.wartezeit_ende and self.wartezeit_aktiv:
            return (self.wartezeit_ende - date.today()).days
        return 0

    def __repr__(self):
        return f'<MedikamentBehandlung {self.medikament_name} Herde={self.herde_id}>'


class FutterLieferung(db.Model):
    """Futtermittel-Dokumentation."""
    __tablename__ = 'futter_lieferung'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'))

    datum = db.Column(db.Date, nullable=False)
    futtermittel = db.Column(db.String(200))
    lieferant = db.Column(db.String(200))
    menge_kg = db.Column(db.Numeric(10, 2))
    charge = db.Column(db.String(100))
    preis = db.Column(db.Numeric(10, 2))

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    herde = db.relationship('Herde', back_populates='futter_lieferungen')

    def __repr__(self):
        return f'<FutterLieferung {self.datum} {self.futtermittel}>'


class SalmonellenProbe(db.Model):
    """Salmonellen-Monitoring."""
    __tablename__ = 'salmonellen_probe'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'), nullable=False)

    probenahme_datum = db.Column(db.Date, nullable=False)
    probenart = db.Column(db.String(50))
    labor = db.Column(db.String(200))
    ergebnis = db.Column(db.String(20))  # positiv / negativ / ausstehend
    ergebnis_datum = db.Column(db.Date)
    massnahmen = db.Column(db.Text)
    serotyp = db.Column(db.String(100))
    beleg_nr = db.Column(db.String(100))

    bemerkung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    herde = db.relationship('Herde', back_populates='salmonellen_proben')

    def __repr__(self):
        return f'<SalmonellenProbe {self.probenahme_datum} {self.ergebnis}>'


class HerdeEreignis(db.Model):
    """Allgemeines Stallbuch-Ereignis."""
    __tablename__ = 'herde_ereignis'

    id = db.Column(db.Integer, primary_key=True)
    herde_id = db.Column(db.Integer, db.ForeignKey('herde.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    kategorie = db.Column(db.String(50))
    beschreibung = db.Column(db.Text)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    herde = db.relationship('Herde', back_populates='ereignisse')

    def __repr__(self):
        return f'<HerdeEreignis {self.datum} {self.kategorie}>'
