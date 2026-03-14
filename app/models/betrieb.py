from datetime import datetime
from app.extensions import db


class Betrieb(db.Model):
    """Betriebsstammdaten."""
    __tablename__ = 'betrieb'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Stammdaten
    name = db.Column(db.String(255), nullable=False)
    beschreibung = db.Column(db.Text)
    
    # Adresse
    strasse = db.Column(db.String(255))
    plz = db.Column(db.String(10))
    ort = db.Column(db.String(120))
    land = db.Column(db.String(2), default='AT')  # ISO 3166-1 alpha-2
    waehrung = db.Column(db.String(5), default='€')  # €, CHF, etc.
    mwst_satz_standard = db.Column(db.Numeric(5, 2), default=20)  # Standard-MwSt in %
    uid_format = db.Column(db.String(30), default='ATU12345678')  # Platzhalter-Beispiel
    
    # Behördlich
    uid_nummer = db.Column(db.String(20))  # UID-Nummer (AT/EU)
    steuernummer = db.Column(db.String(20))
    
    # Bank
    iban = db.Column(db.String(34))
    bic = db.Column(db.String(11))
    bank_name = db.Column(db.String(120))
    
    # Kontakt
    telefon = db.Column(db.String(20))
    email = db.Column(db.String(120))
    website = db.Column(db.String(255))
    
    # Betrieb
    logo_path = db.Column(db.String(255))
    hintergrundbild_path = db.Column(db.String(255))

    # Lizenz / Module
    ist_testbetrieb = db.Column(db.Boolean, default=False)  # Testbetrieb: alle Module aktiv
    modul_legehennen = db.Column(db.Boolean, default=False)
    modul_milchvieh = db.Column(db.Boolean, default=False)

    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Betrieb {self.name}>'
