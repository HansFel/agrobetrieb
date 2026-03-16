from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from app.models.rollen import ist_betriebsadmin

hilfe_bp = Blueprint('hilfe', __name__, url_prefix='/hilfe')


@hilfe_bp.route('/')
@login_required
def index():
    return render_template('hilfe/index.html')


@hilfe_bp.route('/inbetriebnahme')
@login_required
def inbetriebnahme():
    if not ist_betriebsadmin(current_user):
        abort(403)
    return render_template('hilfe/inbetriebnahme.html')
