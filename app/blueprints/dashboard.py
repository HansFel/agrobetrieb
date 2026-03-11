from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models.betrieb import Betrieb

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')


@dashboard_bp.route('/')
@login_required
def index():
    """Dashboard-Startseite."""
    betrieb = Betrieb.query.first()
    context = {
        'betrieb': betrieb,
    }
    return render_template('dashboard/index.html', **context)
