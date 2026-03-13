import os
import click
import subprocess
from flask import Flask, render_template, url_for
from app.config import config
from app.extensions import db, migrate, login_manager, csrf

APP_VERSION = '0.1.0-alpha'

# Build-Referenz: Git Commit Hash oder Fallback
def _get_build_hash():
    # 1. Env-Variable (Docker Build-Arg → ENV)
    env_hash = os.environ.get('COMMIT_HASH')
    if env_hash and env_hash != 'unknown':
        return env_hash
    # 2. Datei /app/BUILD_HASH (vom Dockerfile geschrieben)
    try:
        build_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'BUILD_HASH')
        if os.path.isfile(build_file):
            h = open(build_file).read().strip()
            if h and h != 'unknown':
                return h
    except Exception:
        pass
    # 3. Git direkt aufrufen (lokale Entwicklung)
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=os.path.dirname(os.path.dirname(__file__)),
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass
    return 'unknown'

APP_BUILD = _get_build_hash()


def create_app(config_name='default'):
    """Application Factory."""
    app = Flask(__name__)
    
    # Konfiguration laden
    cfg = config.get(config_name, config['default'])
    app.config.from_object(cfg)
    
    # Extensions initialisieren
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Migrationen und Admin-Erstellung laufen ueber entrypoint.sh (Docker)
    # bzw. manuell via 'flask db upgrade' (lokal)
    
    # User Loader für Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Context Processor für Templates
    @app.context_processor
    def inject_globals():
        from datetime import datetime
        from app.models.betrieb import Betrieb
        from app.models.rollen import hat_berechtigung, hat_modul_zugriff
        
        # Länderspezifische Defaults
        LAENDER = {
            'AT': {'waehrung': '€', 'mwst': 20, 'uid_placeholder': 'ATU12345678', 'land_name': 'Österreich'},
            'DE': {'waehrung': '€', 'mwst': 19, 'uid_placeholder': 'DE123456789', 'land_name': 'Deutschland'},
            'CH': {'waehrung': 'CHF', 'mwst': 8.1, 'uid_placeholder': 'CHE-123.456.789', 'land_name': 'Schweiz'},
            'IT': {'waehrung': '€', 'mwst': 22, 'uid_placeholder': 'IT12345678901', 'land_name': 'Italien'},
            'LI': {'waehrung': 'CHF', 'mwst': 8.1, 'uid_placeholder': 'LI12345', 'land_name': 'Liechtenstein'},
        }
        
        betrieb = Betrieb.query.first()
        land_code = betrieb.land if betrieb else 'AT'
        land_info = LAENDER.get(land_code, LAENDER['AT'])
        
        waehrung = betrieb.waehrung if betrieb and betrieb.waehrung else land_info['waehrung']
        mwst_standard = float(betrieb.mwst_satz_standard) if betrieb and betrieb.mwst_satz_standard else land_info['mwst']
        uid_placeholder = betrieb.uid_format if betrieb and betrieb.uid_format else land_info['uid_placeholder']
        
        return {
            'app_title': 'AgroBetrieb',
            'app_version': APP_VERSION,
            'app_build': APP_BUILD,
            'now': datetime.utcnow(),
            'now_year': datetime.now().year,
            'waehrung': waehrung,
            'land_code': land_code,
            'land_name': land_info['land_name'],
            'mwst_standard': mwst_standard,
            'uid_placeholder': uid_placeholder,
            'laender': LAENDER,
            'betrieb_obj': betrieb,
            'hat_berechtigung': hat_berechtigung,
            'hat_modul_zugriff': hat_modul_zugriff,
        }
    
    # Blueprint registrieren - direkte Modul-Importe um zirkuläre Importe zu vermeiden
    from app.blueprints.auth import auth_bp
    from app.blueprints.dashboard import dashboard_bp
    from app.blueprints.betrieb import betrieb_bp
    from app.blueprints.benutzer import benutzer_bp
    from app.blueprints.maschinen import maschinen_bp
    from app.blueprints.buchhaltung import buchhaltung_bp
    from app.blueprints.fakturierung import fakturierung_bp
    from app.blueprints.lager import lager_bp
    from app.blueprints.datensicherung import datensicherung_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(benutzer_bp)
    app.register_blueprint(betrieb_bp)
    app.register_blueprint(maschinen_bp)
    app.register_blueprint(buchhaltung_bp)
    app.register_blueprint(fakturierung_bp)
    app.register_blueprint(lager_bp)
    app.register_blueprint(datensicherung_bp)
    
    # CLI Commands
    @app.cli.command()
    def init_db():
        """Datenbank initialisieren."""
        db.create_all()
        click.echo('Datenbank initialisiert.')
    
    @app.cli.command()
    def seed_db():
        """Datenbank mit Test-Daten füllen."""
        from app.models.user import User
        from app.models.betrieb import Betrieb
        
        if User.query.first() is None:
            user = User(
                username='admin',
                email='admin@agrobetrieb.local',
                rolle='admin',
                aktiv=True
            )
            user.set_password('admin')
            
            betrieb = Betrieb(
                name='Musterbetrieb',
                strasse='Beispielstrasse 1',
                plz='6900',
                ort='Bregenz',
                land='AT'
            )
            
            db.session.add(user)
            db.session.add(betrieb)
            db.session.commit()
            click.echo('Test-Daten eingefügt.')
        else:
            click.echo('Datenbank is nicht leer.')
    
    # Error Handler
    @app.errorhandler(404)
    def not_found(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    return app
