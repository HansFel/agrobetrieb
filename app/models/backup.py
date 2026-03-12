from datetime import datetime
from app.extensions import db


class Backup(db.Model):
    """Protokoll einer Datensicherung."""
    __tablename__ = 'backup'

    id = db.Column(db.Integer, primary_key=True)
    dateiname = db.Column(db.Text, nullable=False)
    dateipfad = db.Column(db.Text, nullable=False)
    dateigroesse = db.Column(db.BigInteger)  # Bytes
    checksum = db.Column(db.String(64))  # SHA-256
    typ = db.Column(db.String(20), default='manuell')  # 'manuell', 'automatisch'
    status = db.Column(db.String(20), default='erfolgreich')  # 'erfolgreich', 'fehlgeschlagen'
    fehler_meldung = db.Column(db.Text)
    erstellt_von = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    dauer_sekunden = db.Column(db.Float)

    erstellt_von_user = db.relationship('User', foreign_keys=[erstellt_von])

    def __repr__(self):
        return f'<Backup {self.dateiname} {self.status}>'

    @property
    def groesse_formatiert(self):
        if not self.dateigroesse:
            return '–'
        if self.dateigroesse < 1024:
            return f'{self.dateigroesse} B'
        elif self.dateigroesse < 1024 * 1024:
            return f'{self.dateigroesse / 1024:.1f} KB'
        else:
            return f'{self.dateigroesse / (1024 * 1024):.1f} MB'
