from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.db import Base, DATABASE_URL
from app import models

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
# Alembic's ini may not include logging sections in CI; guard fileConfig
if config.config_file_name and os.path.exists(config.config_file_name):
    try:
        fileConfig(config.config_file_name)
    except Exception:
        # ignore logging config errors (missing [formatters] etc.)
        pass

# set sqlalchemy.url from env if provided
if 'DATABASE_URL' in os.environ:
    config.set_main_option('sqlalchemy.url', os.environ['DATABASE_URL'])

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option('sqlalchemy.url')
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(config.get_section(config.config_ini_section), prefix='sqlalchemy.', poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
