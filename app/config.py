import os


class Config:
    """Basis-Konfiguration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-key-agrobetrieb')
    
    # SQLite lokal, PostgreSQL auf Server
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///agrobetrieb.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 7200  # 2 Stunden


class DevelopmentConfig(Config):
    """Entwicklungsumgebung."""
    DEBUG = True


class ProductionConfig(Config):
    """Produktionsumgebung."""
    DEBUG = False


class TestingConfig(Config):
    """Testumgebung."""
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL_TEST',
        'sqlite:////Users/HTFel/OneDrive/MGRsoftware/data/AgroBetrieb/test.db'
    )


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig,
}
