from datetime import datetime
from app.extensions import db


class LagerArtikel(db.Model):
    """Artikel im Lager."""
    __tablename__ = 'lagerartikel'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Grunddaten
    bezeichnung = db.Column(db.String(255), nullable=False)
    beschreibung = db.Column(db.Text)
    artikelnummer = db.Column(db.String(50), unique=True)
    
    # Lager
    einheit = db.Column(db.String(20), default='Stk')  # Stück, kg, l, etc.
    aktueller_bestand = db.Column(db.Numeric(10, 2), default=0)
    mindestbestand = db.Column(db.Numeric(10, 2), default=0)
    
    # Kosten
    letzter_einkaufspreis = db.Column(db.Numeric(10, 2))
    durchschnittswert = db.Column(db.Numeric(12, 2), default=0)
    
    # Status
    aktiv = db.Column(db.Boolean, default=True)
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bewegungen = db.relationship('LagerBewegung', back_populates='artikel', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def unter_mindestbestand(self):
        """True wenn aktueller Bestand unter Mindestbestand."""
        return self.aktueller_bestand < self.mindestbestand
    
    def __repr__(self):
        return f'<LagerArtikel {self.bezeichnung}>'


class LagerBewegung(db.Model):
    """Ein- oder Ausbuchung eines Lagerartikels."""
    __tablename__ = 'lagerbewegung'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Artikel
    artikel_id = db.Column(db.Integer, db.ForeignKey('lagerartikel.id', ondelete='CASCADE'), nullable=False)
    
    # Bewegung
    datum = db.Column(db.Date, nullable=False)
    typ = db.Column(db.String(20), nullable=False)  # 'eingang' oder 'ausgang'
    menge = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Grund
    grund = db.Column(db.String(20))  # 'einkauf', 'verbrauch', 'inventur', 'umbau', etc.
    notiz = db.Column(db.Text)
    
    # Benutzer
    benutzer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Belegnummer (optional)
    beleg_nummer = db.Column(db.String(50))
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    artikel = db.relationship('LagerArtikel', back_populates='bewegungen')
    benutzer = db.relationship('User')
    
    def __repr__(self):
        return f'<LagerBewegung {self.artikel.bezeichnung} {self.typ}>'
