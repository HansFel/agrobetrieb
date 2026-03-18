"""
Externe Apps – konfigurierbare Liste von Ziel-Apps für SSO-Weiterleitungen.

Systemweit vom Superadmin verwaltet.
Pro Betrieb wird gesteuert welche Apps verfügbar sind.
"""
from app.extensions import db


class ExterneApp(db.Model):
    """Eine externe App zu der per SSO weitergeleitet werden kann."""
    __tablename__ = 'externe_app'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)        # Anzeigename, z.B. "Maschinengemeinschaft"
    kuerzel = db.Column(db.String(30), unique=True, nullable=False)  # z.B. "mg", "agr", "gem1"
    basis_url = db.Column(db.String(255), nullable=False)   # z.B. "https://mgrattenberg.duckdns.org/mg"
    icon = db.Column(db.String(50), default='bi-box-arrow-up-right')  # Bootstrap Icons
    beschreibung = db.Column(db.String(255))
    aktiv = db.Column(db.Boolean, default=True, nullable=False)
    reihenfolge = db.Column(db.Integer, default=0)          # Sortierung

    betriebe = db.relationship(
        'BetriebExterneApp', back_populates='app', cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f'<ExterneApp {self.kuerzel}>'


class BetriebExterneApp(db.Model):
    """Verknüpfung: Welche Apps sind für einen Betrieb freigeschaltet."""
    __tablename__ = 'betrieb_externe_app'

    id = db.Column(db.Integer, primary_key=True)
    betrieb_id = db.Column(db.Integer, db.ForeignKey('betrieb.id', ondelete='CASCADE'), nullable=False)
    app_id = db.Column(db.Integer, db.ForeignKey('externe_app.id', ondelete='CASCADE'), nullable=False)

    betrieb = db.relationship('Betrieb', backref=db.backref('externe_apps', lazy='dynamic'))
    app = db.relationship('ExterneApp', back_populates='betriebe')

    __table_args__ = (
        db.UniqueConstraint('betrieb_id', 'app_id', name='uq_betrieb_externe_app'),
    )

    def __repr__(self):
        return f'<BetriebExterneApp betrieb={self.betrieb_id} app={self.app_id}>'
