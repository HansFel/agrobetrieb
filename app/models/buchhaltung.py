from datetime import datetime
from app.extensions import db


class Konto(db.Model):
    """Buchhaltungs-Konto."""
    __tablename__ = 'konto'
    
    id = db.Column(db.Integer, primary_key=True)
    nummer = db.Column(db.String(20), unique=True, nullable=False)
    bezeichnung = db.Column(db.String(255), nullable=False)
    typ = db.Column(db.String(20), nullable=False)  # 'aktiva', 'passiva', 'ertrag', 'aufwand'
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Konto {self.nummer} {self.bezeichnung}>'


class Kategorie(db.Model):
    """Buchungskategorie (für Ausgaben/Einnahmen)."""
    __tablename__ = 'kategorie'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    beschreibung = db.Column(db.Text)
    farbe = db.Column(db.String(7), default='#6c757d')  # Hex-Farbe
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    buchungen = db.relationship('Buchung', back_populates='kategorie', lazy='dynamic')
    
    def __repr__(self):
        return f'<Kategorie {self.name}>'


class Buchung(db.Model):
    """Einzelne Buchung."""
    __tablename__ = 'buchung'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Zeitangaben
    datum = db.Column(db.Date, nullable=False)
    valuta = db.Column(db.Date)  # Zahlungstag
    
    # Konten
    soll_konto_id = db.Column(db.Integer, db.ForeignKey('konto.id'))
    haben_konto_id = db.Column(db.Integer, db.ForeignKey('konto.id'))
    
    # Betrag
    betrag = db.Column(db.Numeric(12, 2), nullable=False)
    
    # Kategorie
    kategorie_id = db.Column(db.Integer, db.ForeignKey('kategorie.id'))
    
    # Details
    beschreibung = db.Column(db.Text, nullable=False)
    beleg_nummer = db.Column(db.String(50))
    
    # MwSt
    mwst_satz = db.Column(db.Numeric(5, 2), default=0)  # z.B. 19 = 19%
    mwst_betrag = db.Column(db.Numeric(12, 2), default=0)
    
    # Status
    bezahlt = db.Column(db.Boolean, default=True)
    
    # Audit
    erstellt_von_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    soll_konto = db.relationship('Konto', foreign_keys=[soll_konto_id], backref='als_soll')
    haben_konto = db.relationship('Konto', foreign_keys=[haben_konto_id], backref='als_haben')
    kategorie = db.relationship('Kategorie', back_populates='buchungen')
    erstellt_von = db.relationship('User')
    
    def __repr__(self):
        return f'<Buchung {self.datum} {self.betrag}>'
