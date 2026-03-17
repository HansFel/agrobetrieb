"""
SSO-Token für Single Sign-On zu MGRSoftware.

Ablauf:
  1. AgroBetrieb erzeugt Token (30 Sek. gültig, einmalig verwendbar)
  2. Redirect zu MGRSoftware mit Token in URL
  3. MGRSoftware löst Token ein → User ist eingeloggt
"""
import secrets
import hmac
import hashlib
import os
from datetime import datetime, timedelta
from app.extensions import db


class SsoToken(db.Model):
    __tablename__ = 'sso_token'

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    username = db.Column(db.String(120), nullable=False)   # Username in AgroBetrieb
    ziel_instanz = db.Column(db.String(50))                # z.B. 'mg', 'agr'
    erstellt_am = db.Column(db.DateTime, default=datetime.utcnow)
    gueltig_bis = db.Column(db.DateTime, nullable=False)
    verwendet = db.Column(db.Boolean, default=False)

    @staticmethod
    def _secret():
        return os.environ.get('SSO_SECRET', 'sso-dev-secret-bitte-aendern')

    @classmethod
    def ausstellen(cls, username: str, ziel_instanz: str = '') -> 'SsoToken':
        """Erstellt ein neues, signiertes SSO-Token (30 Sek. gültig)."""
        raw = secrets.token_hex(20)
        sig = hmac.new(
            cls._secret().encode(),
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        token_str = f'{raw}.{sig}'

        token = cls(
            token=token_str,
            username=username,
            ziel_instanz=ziel_instanz,
            gueltig_bis=datetime.utcnow() + timedelta(seconds=30),
        )
        db.session.add(token)
        db.session.commit()
        return token

    @classmethod
    def einloesen(cls, token_str: str) -> 'SsoToken | None':
        """
        Prüft und markiert Token als verwendet.
        Gibt Token zurück wenn gültig, sonst None.
        """
        if not token_str or '.' not in token_str:
            return None

        raw, sig = token_str.rsplit('.', 1)
        erwartet = hmac.new(
            cls._secret().encode(),
            raw.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        if not hmac.compare_digest(sig, erwartet):
            return None

        token = cls.query.filter_by(token=token_str, verwendet=False).first()
        if not token:
            return None
        if datetime.utcnow() > token.gueltig_bis:
            return None

        token.verwendet = True
        db.session.commit()
        return token

    def __repr__(self):
        return f'<SsoToken {self.username} → {self.ziel_instanz}>'
