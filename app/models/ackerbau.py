"""
Ackerbau-Modul – Datenmodelle.

Modul 1 (modul_ackerbau): Schlagkartei, Spritztagebuch, einfacher Düngerplaner
Modul 2 (modul_ackerbau_pro): NAPV-Düngebedarfsermittlung, Bodenuntersuchung,
                               170kg-Bilanz, Rote Gebiete, Sperrfristen
"""
from datetime import datetime, date
from app.extensions import db


# ---------------------------------------------------------------------------
# KONSTANTEN
# ---------------------------------------------------------------------------

EPPO_KULTUREN = [
    ('TRZAW', 'Winterweizen'),
    ('TRZAS', 'Sommerweizen'),
    ('HORVW', 'Wintergerste'),
    ('HORVS', 'Sommergerste'),
    ('ZEAMX', 'Mais'),
    ('BRSNN', 'Winterraps'),
    ('GLXMA', 'Soja'),
    ('HELAN', 'Sonnenblume'),
    ('AVESA', 'Hafer'),
    ('SECCE', 'Roggen'),
    ('TTLSP', 'Triticale'),
    ('SPQOL', 'Spinat'),
    ('BEAVD', 'Zuckerrübe'),
    ('SOLTU', 'Kartoffel'),
    ('PHSVX', 'Bohne'),
    ('PISSX', 'Erbse'),
    ('MEDSA', 'Luzerne'),
    ('TRZDU', 'Hartweizen/Durum'),
    ('LOLPE', 'Weidelgras'),
    ('DACGL', 'Knaulgras'),
    ('POAPR', 'Wiesenrispe'),
    ('FESAR', 'Rotschwingel'),
]

SPRITZMITTEL_KATEGORIEN = [
    'Herbizid',
    'Fungizid',
    'Insektizid',
    'Akarizid',
    'Wachstumsregler',
    'Molluskizid',
    'Rodentizid',
    'Saatgutbehandlung',
    'Sonstiges',
]

SPRITZMITTEL_EINHEITEN = [
    ('l/ha', 'Liter pro Hektar'),
    ('kg/ha', 'Kilogramm pro Hektar'),
    ('ml/ha', 'Milliliter pro Hektar'),
    ('g/ha', 'Gramm pro Hektar'),
]

BBCH_STADIEN = [
    ('00', '00 – Trockener Samen'),
    ('09', '09 – Auflaufen'),
    ('10', '10 – Erstes Blatt'),
    ('12', '12 – 2 Blätter'),
    ('13', '13 – 3 Blätter'),
    ('21', '21 – Bestockungsbeginn'),
    ('25', '25 – 5 Bestockungstriebe'),
    ('30', '30 – Schossbeginn'),
    ('31', '31 – 1-Knoten-Stadium'),
    ('32', '32 – 2-Knoten-Stadium'),
    ('37', '37 – Fahnenblatt sichtbar'),
    ('39', '39 – Fahnenblatt entfaltet'),
    ('51', '51 – Ährenschieben Beginn'),
    ('59', '59 – Ähre voll sichtbar'),
    ('61', '61 – Blüte Beginn'),
    ('69', '69 – Blüte Ende'),
    ('71', '71 – Kornbildung wässrig'),
    ('75', '75 – Milchreife'),
    ('85', '85 – Teigreife'),
    ('87', '87 – Gelbreife'),
    ('89', '89 – Vollreife'),
    ('92', '92 – Totreife'),
]

DUENGER_ARTEN = [
    ('mineral', 'Mineraldünger'),
    ('wirtschafts_guelle', 'Wirtschaftsdünger – Gülle'),
    ('wirtschafts_mist', 'Wirtschaftsdünger – Mist'),
    ('wirtschafts_jauche', 'Wirtschaftsdünger – Jauche'),
    ('kompost', 'Kompost'),
    ('organisch', 'Organischer Handelsdünger'),
    ('boden', 'Bodenverbesserungsmittel'),
]

DUENGER_EINHEITEN = [
    ('kg/ha', 'kg pro Hektar'),
    ('t/ha', 'Tonnen pro Hektar'),
    ('m3/ha', 'm³ pro Hektar'),
    ('l/ha', 'Liter pro Hektar'),
]

BODENARTEN = [
    'Sand', 'Lehmiger Sand', 'Sandiger Lehm', 'Lehm',
    'Toniger Lehm', 'Ton', 'Schluff', 'Humus',
]

AUSBRINGVERFAHREN = [
    'Breitstreuer',
    'Schleppschlauch',
    'Schleppfuß',
    'Injektion',
    'Unterblattdüsung',
    'Druckfass',
    'Festmiststreuer',
    'Sonstiges',
]

# Pro-Modul: Tierkateg. für N-Anfall (ÖPUL/AT-Werte kg N/Tier/Jahr)
TIERKATEGORIEN_N = {
    'Milchkuh > 6000 l': 120,
    'Milchkuh 4000–6000 l': 100,
    'Milchkuh < 4000 l': 85,
    'Mutterkuh': 65,
    'Jungrind 1–2 Jahre': 55,
    'Kalb bis 1 Jahr': 30,
    'Mastbulle': 55,
    'Zuchtsau': 14,
    'Mastschwein': 10,
    'Ferkel': 3,
    'Legehenne': 0.7,
    'Masthähnchen': 0.7,
    'Truthahn': 2.5,
    'Schaf / Ziege': 12,
    'Pferd': 55,
}

# ---------------------------------------------------------------------------
# MODELLE – Modul 1 (einfach)
# ---------------------------------------------------------------------------

class Schlag(db.Model):
    """Schlag/Feld eines Betriebs."""
    __tablename__ = 'schlag'

    id = db.Column(db.Integer, primary_key=True)
    betrieb_id = db.Column(db.Integer, db.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    flaeche_ha = db.Column(db.Numeric(10, 4))
    feldstueck_nr = db.Column(db.String(50))       # INVEKOS-Feldstück
    invekos_flaeche = db.Column(db.Numeric(10, 4)) # Fläche laut INVEKOS-GIS
    bodenart = db.Column(db.String(50))
    notizen = db.Column(db.Text)

    aktiv = db.Column(db.Boolean, default=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    betrieb = db.relationship('Betrieb', backref=db.backref('schlaege', lazy='dynamic'))
    kulturen = db.relationship('SchlagKultur', backref='schlag', lazy='dynamic',
                               order_by='desc(SchlagKultur.aussaat_datum)')
    spritzungen = db.relationship('Spritzung', backref='schlag', lazy='dynamic',
                                  order_by='desc(Spritzung.datum)')
    duengungen = db.relationship('Duengung', backref='schlag', lazy='dynamic',
                                 order_by='desc(Duengung.datum)')

    @property
    def aktive_kultur(self):
        return self.kulturen.filter_by(ernte_datum=None).first()

    def __repr__(self):
        return f'<Schlag {self.name}>'


class SchlagKultur(db.Model):
    """Kultur/Anbau auf einem Schlag (Saat bis Ernte)."""
    __tablename__ = 'schlag_kultur'

    id = db.Column(db.Integer, primary_key=True)
    schlag_id = db.Column(db.Integer, db.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False)

    kultur_code = db.Column(db.String(20), nullable=False)  # EPPO-Code
    kultur_name = db.Column(db.String(100), nullable=False)
    sorte = db.Column(db.String(100))
    aussaat_datum = db.Column(db.Date, nullable=False)
    ernte_datum = db.Column(db.Date, nullable=True)         # NULL = aktiv

    # Saat-Wizard Felder
    saatmenge_kg_ha = db.Column(db.Numeric(8, 2))            # berechnete Saatmenge
    saatmenge_tatsaechlich_kg_ha = db.Column(db.Numeric(8, 2))  # tatsächlicher Verbrauch

    bemerkungen = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    spritzungen = db.relationship('Spritzung', backref='kultur', lazy='dynamic')

    @property
    def ist_aktiv(self):
        return self.ernte_datum is None

    @property
    def status_text(self):
        if self.ernte_datum:
            return f"Geerntet {self.ernte_datum.strftime('%d.%m.%Y')}"
        return 'Aktiv'

    def __repr__(self):
        return f'<SchlagKultur {self.kultur_name} auf Schlag {self.schlag_id}>'


class Spritzmittel(db.Model):
    """Pflanzenschutzmittel-Stammdaten eines Betriebs."""
    __tablename__ = 'spritzmittel'

    id = db.Column(db.Integer, primary_key=True)
    betrieb_id = db.Column(db.Integer, db.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False)

    name = db.Column(db.String(100), nullable=False)
    wirkstoff = db.Column(db.String(200))
    zulassungsnummer = db.Column(db.String(50))
    registernummer = db.Column(db.String(50))
    kategorie = db.Column(db.String(50))
    einheit = db.Column(db.String(20), default='l/ha')

    aktiv = db.Column(db.Boolean, default=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    betrieb = db.relationship('Betrieb', backref='spritzmittel')
    spritzungen = db.relationship('Spritzung', backref='spritzmittel', lazy='dynamic')

    def __repr__(self):
        return f'<Spritzmittel {self.name}>'


class Spritzung(db.Model):
    """Pflanzenschutzmittel-Anwendung auf einem Schlag (Spritztagebuch)."""
    __tablename__ = 'spritzung'

    id = db.Column(db.Integer, primary_key=True)
    schlag_id = db.Column(db.Integer, db.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False)
    schlag_kultur_id = db.Column(db.Integer, db.ForeignKey('schlag_kultur.id', ondelete='SET NULL'), nullable=True)
    spritzmittel_id = db.Column(db.Integer, db.ForeignKey('spritzmittel.id', ondelete='RESTRICT'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    uhrzeit = db.Column(db.Time, nullable=True)

    bbch_stadium = db.Column(db.String(10))
    aufwandmenge = db.Column(db.Numeric(10, 3), nullable=False)  # Menge pro ha

    invekos_flaeche = db.Column(db.Numeric(10, 4))    # Schlaggröße INVEKOS
    behandelte_flaeche = db.Column(db.Numeric(10, 4)) # tatsächlich behandelt

    bemerkungen = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def gesamtmenge(self):
        if self.aufwandmenge and self.behandelte_flaeche:
            return float(self.aufwandmenge) * float(self.behandelte_flaeche)
        return None

    def __repr__(self):
        return f'<Spritzung {self.id} auf Schlag {self.schlag_id}>'


class Duengung(db.Model):
    """Einzelne Düngegabe auf einem Schlag."""
    __tablename__ = 'duengung'

    id = db.Column(db.Integer, primary_key=True)
    schlag_id = db.Column(db.Integer, db.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False)
    kultur_id = db.Column(db.Integer, db.ForeignKey('schlag_kultur.id', ondelete='SET NULL'), nullable=True)

    datum = db.Column(db.Date, nullable=False, default=date.today)
    duenger_art = db.Column(db.String(50), nullable=False)
    duenger_name = db.Column(db.String(100))

    n_gehalt = db.Column(db.Numeric(8, 2))  # kg N je Einheit
    p_gehalt = db.Column(db.Numeric(8, 2))  # kg P₂O₅ je Einheit
    k_gehalt = db.Column(db.Numeric(8, 2))  # kg K₂O je Einheit

    menge = db.Column(db.Numeric(10, 2), nullable=False)
    einheit = db.Column(db.String(20), default='kg/ha')
    behandelte_flaeche = db.Column(db.Numeric(10, 2))

    # Berechnete Nährstoffmengen (kg/ha)
    n_ausgebracht = db.Column(db.Numeric(10, 2))
    p_ausgebracht = db.Column(db.Numeric(10, 2))
    k_ausgebracht = db.Column(db.Numeric(10, 2))

    ausbringverfahren = db.Column(db.String(50))
    einarbeitung = db.Column(db.Boolean, default=False)
    bemerkungen = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    kultur = db.relationship('SchlagKultur', backref=db.backref('duengungen', lazy='dynamic'),
                             foreign_keys=[kultur_id])

    def __repr__(self):
        return f'<Duengung {self.id}: {self.duenger_name} auf Schlag {self.schlag_id}>'


# ---------------------------------------------------------------------------
# MODELLE – Modul 2 Pro (NAPV / erweitert)
# ---------------------------------------------------------------------------

class Bodenuntersuchung(db.Model):
    """Bodenuntersuchungsergebnisse je Schlag."""
    __tablename__ = 'bodenuntersuchung'

    id = db.Column(db.Integer, primary_key=True)
    schlag_id = db.Column(db.Integer, db.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False)

    datum = db.Column(db.Date, nullable=False)
    labor = db.Column(db.String(100))

    # Nährstoffe (mg/100g Boden)
    ph_wert = db.Column(db.Numeric(4, 2))
    p_gehalt = db.Column(db.Numeric(8, 2))   # P₂O₅ mg/100g
    k_gehalt = db.Column(db.Numeric(8, 2))   # K₂O mg/100g
    mg_gehalt = db.Column(db.Numeric(8, 2))  # Mg mg/100g
    humus = db.Column(db.Numeric(5, 2))       # % Humus

    # Gehaltsklassen (A=sehr niedrig … E=sehr hoch)
    p_klasse = db.Column(db.String(1))
    k_klasse = db.Column(db.String(1))
    mg_klasse = db.Column(db.String(1))

    bemerkungen = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    schlag = db.relationship('Schlag', backref=db.backref('bodenuntersuchungen', lazy='dynamic'))

    def __repr__(self):
        return f'<Bodenuntersuchung {self.id} Schlag {self.schlag_id} {self.datum}>'


class Duengebedarfsermittlung(db.Model):
    """
    NAPV-konforme Düngebedarfsermittlung je Schlag und Jahr.
    (Nitrat-Aktionsprogramm-Verordnung / Rote Gebiete)
    """
    __tablename__ = 'duengebedarfsermittlung'

    id = db.Column(db.Integer, primary_key=True)
    schlag_id = db.Column(db.Integer, db.ForeignKey('schlag.id', ondelete='CASCADE'), nullable=False)
    kultur_id = db.Column(db.Integer, db.ForeignKey('schlag_kultur.id', ondelete='SET NULL'), nullable=True)

    jahr = db.Column(db.Integer, nullable=False)

    # Kulturparameter
    ertragsziel_dt_ha = db.Column(db.Numeric(8, 2))
    n_bedarf_brutto = db.Column(db.Numeric(8, 2))   # kg N/ha Gesamtbedarf
    n_bedarf_netto = db.Column(db.Numeric(8, 2))    # nach Abzügen

    # Abzüge
    n_nachlieferung_boden = db.Column(db.Numeric(8, 2))  # Boden-Nmin / Humus
    n_aus_vorfrucht = db.Column(db.Numeric(8, 2))
    n_aus_wirtschaft = db.Column(db.Numeric(8, 2))   # berechnete Wirtschaftsdünger-N

    # Rotes Gebiet
    ist_rotes_gebiet = db.Column(db.Boolean, default=False)
    reduktion_rotes_gebiet = db.Column(db.Numeric(5, 2), default=20)  # % Reduktion

    # Ergebnis
    n_mineraldung_empfehlung = db.Column(db.Numeric(8, 2))  # kg N/ha Mineraldünger
    kommentar = db.Column(db.Text)

    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    schlag = db.relationship('Schlag', backref=db.backref('bedarfsermittlungen', lazy='dynamic'))
    kultur = db.relationship('SchlagKultur', foreign_keys=[kultur_id])

    def __repr__(self):
        return f'<Duengebedarfsermittlung {self.id} Schlag {self.schlag_id} {self.jahr}>'


class Tierbestand(db.Model):
    """Tierbestand für N-Anfall-Berechnung (170 kg N/ha Bilanz)."""
    __tablename__ = 'tierbestand'

    id = db.Column(db.Integer, primary_key=True)
    betrieb_id = db.Column(db.Integer, db.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False)

    jahr = db.Column(db.Integer, nullable=False)
    tier_kategorie = db.Column(db.String(100), nullable=False)
    haltungsform = db.Column(db.String(50))  # guelle, mist, tiefstall
    anzahl = db.Column(db.Numeric(10, 2), nullable=False)

    # Berechnete N-Werte
    n_anfall_jahr = db.Column(db.Numeric(10, 2))     # kg N gesamt
    n_feldfallend = db.Column(db.Numeric(10, 2))     # kg N feldfallend

    bemerkungen = db.Column(db.Text)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    betrieb = db.relationship('Betrieb', backref=db.backref('tierbestaende', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('betrieb_id', 'jahr', 'tier_kategorie', 'haltungsform',
                            name='uq_tierbestand_betrieb_jahr_tier'),
    )

    def __repr__(self):
        return f'<Tierbestand {self.anzahl}x {self.tier_kategorie} {self.jahr}>'
