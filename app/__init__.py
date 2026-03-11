import os
import click
from flask import Flask, render_template, url_for
from app.config import config
from app.extensions import db, migrate, login_manager, csrf

APP_VERSION = '0.1.0-alpha'
APP_BUILD = os.environ.get('COMMIT_HASH', 'dev')


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
    
    # User Loader für Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Context Processor für Templates
    @app.context_processor
    def inject_globals():
        return {
            'app_title': 'AgroBetrieb',
            'app_version': APP_VERSION,
        }
    
    # Blueprint registrieren
    from app.blueprints import auth, dashboard, betrieb
    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(dashboard.dashboard_bp)
    app.register_blueprint(betrieb.betrieb_bp)
    
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
    
    with app.app_context():
        db.create_all()
    
    return app
