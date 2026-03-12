"""
Decorators für Berechtigungsschutz auf Routes.
"""
from functools import wraps
from flask import redirect, url_for, abort, flash, request
from flask_login import current_user
from app.models.rollen import hat_berechtigung


def requires_permission(modul, aktion='view'):
    """
    Decorator: Prüft Berechtigung für Modul+Aktion.
    
    Beispiel:
        @app.route('/buchhaltung/journal')
        @requires_permission('buchhaltung', 'view')
        def journal():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Anmeldung erforderlich', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if not hat_berechtigung(current_user, modul, aktion):
                flash('Keine Berechtigung für diese Aktion', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requires_role(*roles):
    """
    Decorator: Prüft ob Benutzer eine der angegebenen Rollen hat.
    
    Beispiel:
        @app.route('/benutzer')
        @requires_role('betriebsadmin')
        def benutzer_verwaltung():
            ...
    
    Oder mehrere Rollen:
        @requires_role('betriebsadmin', 'mitglied')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Anmeldung erforderlich', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.rolle not in roles:
                flash('Ihre Rolle hat keine Berechtigung für diese Seite', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def requires_admin():
    """Decorator: Nur Betriebsadmin."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Anmeldung erforderlich', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            if current_user.rolle != 'betriebsadmin':
                flash('Nur Administratoren dürfen auf diese Seite zugreifen', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
