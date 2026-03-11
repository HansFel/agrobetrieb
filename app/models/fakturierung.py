from datetime import datetime
from app.extensions import db


class Kunde(db.Model):
    """Kunde für Rechnungen."""
    __tablename__ = 'kunde'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Grunddaten
    name = db.Column(db.String(255), nullable=False)
    beschreibung = db.Column(db.Text)
    
    # Adresse
    strasse = db.Column(db.String(255))
    plz = db.Column(db.String(10))
    ort = db.Column(db.String(120))
    land = db.Column(db.String(2), default='AT')
    
    # Details
    uid_nummer = db.Column(db.String(20))
    kontakt = db.Column(db.String(255))
    
    # Kontakt
    email = db.Column(db.String(120))
    telefon = db.Column(db.String(20))
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    rechnungen = db.relationship('Rechnung', back_populates='kunde', lazy='dynamic')
    
    def __repr__(self):
        return f'<Kunde {self.name}>'


class Rechnung(db.Model):
    """Ausgangsrechnung."""
    __tablename__ = 'rechnung'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Nummern
    nummer = db.Column(db.String(50), unique=True, nullable=False)
    
    # Kunde
    kunde_id = db.Column(db.Integer, db.ForeignKey('kunde.id'), nullable=False)
    
    # Daten
    datum = db.Column(db.Date, nullable=False)
    faellig_am = db.Column(db.Date)
    
    # Status
    status = db.Column(db.String(20), default='offen')  # 'offen', 'bezahlt', 'storno'
    
    # Beträge
    netto_gesamt = db.Column(db.Numeric(12, 2), default=0)
    mwst_gesamt = db.Column(db.Numeric(12, 2), default=0)
    brutto_gesamt = db.Column(db.Numeric(12, 2), default=0)
    
    # Notizen
    notiz = db.Column(db.Text)
    
    # Audit
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    kunde = db.relationship('Kunde', back_populates='rechnungen')
    positionen = db.relationship('RechnungsPosition', back_populates='rechnung', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Rechnung {self.nummer}>'


class RechnungsPosition(db.Model):
    """Position auf einer Rechnung."""
    __tablename__ = 'rechnungsposition'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Rechnung
    rechnung_id = db.Column(db.Integer, db.ForeignKey('rechnung.id', ondelete='CASCADE'), nullable=False)
    
    # Position
    position = db.Column(db.Integer, default=1)  # Reihenfolge
    beschreibung = db.Column(db.String(255), nullable=False)
    
    # Menge & Preis
    menge = db.Column(db.Numeric(10, 2), nullable=False)
    einheit = db.Column(db.String(20), default='Stk')  # Stück, h (Stunden), km, etc.
    einzelpreis = db.Column(db.Numeric(10, 2), nullable=False)
    
    # MwSt
    mwst_satz = db.Column(db.Numeric(5, 2), default=0)
    
    # Gesamtbetrag
    netto = db.Column(db.Numeric(12, 2), nullable=False)
    mwst = db.Column(db.Numeric(12, 2), default=0)
    brutto = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Relationships
    rechnung = db.relationship('Rechnung', back_populates='positionen')
    
    def __repr__(self):
        return f'<RechnungsPosition {self.rechnung.nummer}>'
