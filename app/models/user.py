"""
Benutzer-Modell für AgroBetrieb.

Rollen:
- betriebsadmin: Admin (vollständiger Zugriff, verwaltet Benutzer)
- mitglied: Mitglied/Genosse (vollständiger Zugriff wie Admin, außer Benutzerverwaltung)
- buchhaltung: Buchhaltung (nur Buchhaltungs-Module)
- gelegentlich: Gelegentlicher Mitarbeiter (nur Arbeitsdaten eingeben)
- praktikand: Praktikand (Lesezugriff + Arbeitsdaten)
- packstelle: Packstelle (externer Zugang, nur Sortierergebnisse)
"""
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app.extensions import db


class User(UserMixin, db.Model):
    """Benutzer für AgroBetrieb."""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # Stammdaten
    vorname = db.Column(db.String(120))
    nachname = db.Column(db.String(120))
    telefon = db.Column(db.String(20))
    
    # Status & Rolle
    # Mögliche Rollen: betriebsadmin, mitglied, buchhaltung, gelegentlich, praktikand, packstelle
    rolle = db.Column(db.String(30), default='praktikand')
    aktiv = db.Column(db.Boolean, default=True)
    ist_superadmin = db.Column(db.Boolean, default=False)  # Nur MGRSoftware-Entwickler
    muss_passwort_aendern = db.Column(db.Boolean, default=False)
    
    # Packstelle-Felder (nur bei Rolle 'packstelle')
    packstelle_name = db.Column(db.String(200))
    packstelle_ort = db.Column(db.String(200))
    packstelle_nr = db.Column(db.String(50))
    
    # Timestamps
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    letzter_login = db.Column(db.DateTime)
    
    def set_password(self, password):
        """Passwort hashen und abspeichern."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Passwort prüfen."""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """Ist Betriebsadmin?"""
        return self.rolle == 'betriebsadmin' and self.aktiv
    
    def is_active(self):
        """Ist aktiv?"""
        return self.aktiv
    
    @property
    def rolle_name(self):
        """Lesbare Rolle."""
        from app.models.rollen import ROLLEN
        rollen_info = ROLLEN.get(self.rolle, {})
        return rollen_info.get('name', self.rolle)
    
    def __repr__(self):
        return f'<User {self.username} ({self.rolle})>'
