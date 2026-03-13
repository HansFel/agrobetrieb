"""Alembic environment configuration."""
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
from app.extensions import db
from app import create_app

# this is the Alembic Config object
config = context.config

# Interpret the config file for the logging system
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object for 'autogenerate' support
target_metadata = db.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    import os
    os.environ['ALEMBIC_RUNNING'] = '1'
    app = create_app()
    with app.app_context():
        configuration = config.get_section(config.config_ini_section)
        configuration["sqlalchemy.url"] = app.config["SQLALCHEMY_DATABASE_URI"]
        engine = engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata,
                render_as_batch=True,  # SQLite-kompatibles ALTER TABLE
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
