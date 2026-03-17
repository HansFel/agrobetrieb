"""
SSO-Blueprint für AgroBetrieb.

Routen:
  GET  /sso/zu/<instanz>   – Token ausstellen + Redirect zu MGRSoftware
  GET  /sso/eingang        – Token empfangen (falls AgroBetrieb Ziel ist, Reserveroute)
"""
import os
from flask import Blueprint, redirect, url_for, abort, request, current_app
from flask_login import login_required, current_user
from app.models.sso_token import SsoToken

sso_bp = Blueprint('sso', __name__, url_prefix='/sso')

# Basis-URLs der MGRSoftware-Instanzen (aus Env oder Fallback)
# Format: INSTANZ_NAME → Basis-URL der Instanz
def _mgr_basis_url(instanz: str) -> str:
    """Gibt die Basis-URL der MGRSoftware-Instanz zurück."""
    env_key = f'MGR_URL_{instanz.upper()}'
    url = os.environ.get(env_key, '').rstrip('/')
    if url:
        return url
    # Fallback: gleiche Domain, Prefix /<instanz>
    domain = os.environ.get('DOMAIN', 'localhost')
    return f'https://{domain}/{instanz}'


@sso_bp.route('/zu/<instanz>')
@login_required
def zu_mgrsoftware(instanz: str):
    """
    Stellt SSO-Token aus und leitet zu MGRSoftware weiter.
    Der User landet direkt eingeloggt in MGRSoftware.
    """
    erlaubte = os.environ.get('SSO_INSTANZEN', 'mg,agr,gem1,gem2,gem3,gem4,gem5').split(',')
    if instanz not in erlaubte:
        abort(404)

    token = SsoToken.ausstellen(
        username=current_user.username,
        ziel_instanz=instanz,
    )

    basis = _mgr_basis_url(instanz)
    ziel_url = f'{basis}/auth/sso-eingang?token={token.token}'
    return redirect(ziel_url)
