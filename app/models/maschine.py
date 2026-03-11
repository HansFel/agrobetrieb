from datetime import datetime
from app.extensions import db


class Maschine(db.Model):
    """Maschine im Betrieb."""
    __tablename__ = 'maschine'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Stammdaten
    name = db.Column(db.String(255), nullable=False)
    beschreibung = db.Column(db.Text)
    kennzeichen = db.Column(db.String(50))  # Nummernschild / Kennung
    baujahr = db.Column(db.Integer)
    
    # Status
    aktiv = db.Column(db.Boolean, default=True)
    gesperrt = db.Column(db.Boolean, default=False)
    sperrgrund = db.Column(db.Text)
    
    # Buchungsmodus
    buchungsmodus = db.Column(db.String(20), default='direkt')  # 'direkt' oder 'fortlaufend'
    zaehler_format = db.Column(db.String(20), default='dezimal')  # 'dezimal' oder 'hhmm'
    
    # Kosten
    kosten_pro_einheit = db.Column(db.Numeric(10, 2))
    einheit = db.Column(db.String(50), default='h')  # z.B. 'h' (Stunden), 'km', etc.
    
    # Anschaffung & Abschreibung
    anschaffungswert = db.Column(db.Numeric(12, 2))
    anschaffungsdatum = db.Column(db.Date)
    abschreibungsdauer = db.Column(db.Integer)  # Jahre
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    einsaetze = db.relationship('Einsatz', back_populates='maschine', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Maschine {self.name}>'


class Einsatz(db.Model):
    """Einsatzprotokoll – Durchführung einer Maschine."""
    __tablename__ = 'einsatz'
    
    id = db.Column(db.Integer, primary_key=True)
    maschine_id = db.Column(db.Integer, db.ForeignKey('maschine.id', ondelete='CASCADE'), nullable=False)
    
    # Benutzer
    erstellt_von_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Datum & Zeit
    datum = db.Column(db.Date, nullable=False)
    von = db.Column(db.Time)
    bis = db.Column(db.Time)
    
    # Erfassung
    menge = db.Column(db.Numeric(10, 2), nullable=False)  # Menge/Dauer
    notiz = db.Column(db.Text)
    
    # Zählerstände (für fortlaufenden Modus)
    zaehlerstand_start = db.Column(db.String(50))
    zaehlerstand_ende = db.Column(db.String(50))
    
    # Kosten
    kostenart = db.Column(db.String(50))  # z.B. 'reparatur', 'betriebsstoff', etc.
    kosten = db.Column(db.Numeric(10, 2))
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    aktualisiert_am = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    maschine = db.relationship('Maschine', back_populates='einsaetze')
    erstellt_von = db.relationship('User')
    
    def __repr__(self):
        return f'<Einsatz {self.maschine.name} {self.datum}>'
