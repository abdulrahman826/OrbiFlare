import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["FIRMS_AUTO_SYNC"] = "false"   # tests must never reach the network or purge data

import pytest

from app.config import get_settings
from app.storage.database import Base, SessionLocal, engine


@pytest.fixture()
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def settings():
    return get_settings()
