from app.db import engine, Base
from app import models
from sqlalchemy import inspect


def test_models_create_all():
    # Use SQLAlchemy create_all on test DB (sqlite file) to validate schema
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    assert 'users' in inspector.get_table_names()
    assert 'services' in inspector.get_table_names()
