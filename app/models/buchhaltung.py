from datetime import datetime
from app.extensions import db


class Konto(db.Model):
    """Buchhaltungs-Konto (doppelte Buchführung)."""
    __tablename__ = 'konto'

    id = db.Column(db.Integer, primary_key=True)

    # Kontonummer & Bezeichnung
    kontonummer = db.Column(db.Text, nullable=False, unique=True)
    bezeichnung = db.Column(db.Text, nullable=False)

    # Klassifizierung
    kontenklasse = db.Column(db.Integer, nullable=False)  # 0-9
    kontotyp = db.Column(db.Text, nullable=False)  # 'aktiv', 'passiv', 'aufwand', 'ertrag'

    # Verknuepfungen (optional)
    maschine_id = db.Column(db.Integer, db.ForeignKey('maschine.id'), nullable=True)

    # Einstellungen
    jahresuebertrag = db.Column(db.Boolean, default=False)
    ist_sammelkonto = db.Column(db.Boolean, default=False)
    ist_importkonto = db.Column(db.Boolean, default=False)

    # Status
    aktiv = db.Column(db.Boolean, default=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    maschine = db.relationship('Maschine', backref='konten')
    salden = db.relationship('KontoSaldo', back_populates='konto', lazy='dynamic')

    def __repr__(self):
        return f'<Konto {self.kontonummer} {self.bezeichnung}>'


class KontoSaldo(db.Model):
    """Jahres-Saldo pro Konto."""
    __tablename__ = 'kontosaldo'

    id = db.Column(db.Integer, primary_key=True)
    konto_id = db.Column(db.Integer, db.ForeignKey('konto.id', ondelete='CASCADE'), nullable=False)
    geschaeftsjahr = db.Column(db.Integer, nullable=False)

    # Salden
    saldo_beginn = db.Column(db.Numeric(12, 2), default=0)
    saldo_aktuell = db.Column(db.Numeric(12, 2), default=0)

    # Bewegungen
    summe_soll = db.Column(db.Numeric(12, 2), default=0)
    summe_haben = db.Column(db.Numeric(12, 2), default=0)

    # Zeitstempel
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('konto_id', 'geschaeftsjahr', name='uq_konto_geschaeftsjahr'),
    )

    # Relationships
    konto = db.relationship('Konto', back_populates='salden')

    def __repr__(self):
        return f'<KontoSaldo konto={self.konto_id} jahr={self.geschaeftsjahr}>'


class Buchung(db.Model):
    """Einzelne Buchung (doppelte Buchführung)."""
    __tablename__ = 'buchung'

    id = db.Column(db.Integer, primary_key=True)
    geschaeftsjahr = db.Column(db.Integer, nullable=False)

    # Buchungsdaten
    buchungsnummer = db.Column(db.Text, nullable=False)
    datum = db.Column(db.Date, nullable=False)
    valuta = db.Column(db.Date)

    # Soll/Haben
    soll_konto_id = db.Column(db.Integer, db.ForeignKey('konto.id'), nullable=True)
    haben_konto_id = db.Column(db.Integer, db.ForeignKey('konto.id'), nullable=True)
    betrag = db.Column(db.Numeric(12, 2), nullable=False)

    # Details
    buchungstext = db.Column(db.Text, nullable=False)
    beleg_nummer = db.Column(db.Text)
    beleg_datum = db.Column(db.Date)

    # Verknuepfungen (optional)
    einsatz_id = db.Column(db.Integer, nullable=True)
    bank_transaktion_id = db.Column(db.Integer, nullable=True)

    # Buchungsart
    buchungsart = db.Column(db.Text, default='manuell')

    # Sammelbuchung
    sammel_id = db.Column(db.Integer, nullable=True)

    # Audit
    erstellt_von = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    storniert = db.Column(db.Boolean, default=False)
    storniert_am = db.Column(db.DateTime)
    storniert_von = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('geschaeftsjahr', 'buchungsnummer', name='uq_buchung_nummer'),
    )

    # Relationships
    soll_konto = db.relationship('Konto', foreign_keys=[soll_konto_id])
    haben_konto = db.relationship('Konto', foreign_keys=[haben_konto_id])
    erstellt_von_user = db.relationship('User', foreign_keys=[erstellt_von])
    storniert_von_user = db.relationship('User', foreign_keys=[storniert_von])

    def __repr__(self):
        return f'<Buchung {self.buchungsnummer} {self.betrag}>'


class Buchungsschluessel(db.Model):
    """Buchungsschlüssel / Buchungsvorlage für Bank-Import."""
    __tablename__ = 'buchungsschluessel'

    id = db.Column(db.Integer, primary_key=True)

    kuerzel = db.Column(db.Text, nullable=False, unique=True)
    bezeichnung = db.Column(db.Text, nullable=False)
    buchungstext = db.Column(db.Text)

    # Kontenklassen-Filter (kommasepariert)
    soll_klassen = db.Column(db.Text)
    haben_klassen = db.Column(db.Text)

    # Optional: Spezifische Default-Konten
    soll_konto_id = db.Column(db.Integer, db.ForeignKey('konto.id'), nullable=True)
    haben_konto_id = db.Column(db.Integer, db.ForeignKey('konto.id'), nullable=True)

    # Bank-Import: Suchbegriffe (kommasepariert)
    suchbegriffe = db.Column(db.Text, nullable=True)

    sortierung = db.Column(db.Integer, default=0)
    aktiv = db.Column(db.Boolean, default=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    soll_konto = db.relationship('Konto', foreign_keys=[soll_konto_id])
    haben_konto = db.relationship('Konto', foreign_keys=[haben_konto_id])

    def soll_klassen_liste(self):
        if not self.soll_klassen:
            return []
        return [int(k.strip()) for k in self.soll_klassen.split(',') if k.strip().isdigit()]

    def haben_klassen_liste(self):
        if not self.haben_klassen:
            return []
        return [int(k.strip()) for k in self.haben_klassen.split(',') if k.strip().isdigit()]

    def __repr__(self):
        return f'<Buchungsschluessel {self.kuerzel} "{self.bezeichnung}">'


class BankImportConfig(db.Model):
    """CSV-Konfiguration für Bank-Import."""
    __tablename__ = 'bank_import_config'

    id = db.Column(db.Integer, primary_key=True)

    bank_name = db.Column(db.Text)

    # Spaltenindizes (0-basiert)
    spalte_datum = db.Column(db.Integer, nullable=False, default=0)
    spalte_valuta = db.Column(db.Integer)
    spalte_betrag = db.Column(db.Integer, nullable=False, default=1)
    spalte_text = db.Column(db.Integer, nullable=False, default=2)
    spalte_referenz = db.Column(db.Integer)

    # CSV-Format
    trennzeichen = db.Column(db.Text, default=';')
    datumsformat = db.Column(db.Text, default='%d.%m.%Y')
    dezimaltrennzeichen = db.Column(db.Text, default=',')
    kopfzeilen_ueberspringen = db.Column(db.Integer, default=1)
    encoding = db.Column(db.Text, default='utf-8-sig')

    # Verhalten
    vorzeichen_umkehren = db.Column(db.Boolean, default=False)

    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<BankImportConfig bank={self.bank_name}>'
