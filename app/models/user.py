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
    
    # Status
    rolle = db.Column(db.String(20), default='mitarbeiter')
    # 'admin', 'mitarbeiter', 'readonly'
    aktiv = db.Column(db.Boolean, default=True)
    
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
        """Admin-Check."""
        return self.rolle == 'admin' and self.aktiv
    
    def __repr__(self):
        return f'<User {self.username}>'
