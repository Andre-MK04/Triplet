import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.db import models  # noqa: F401
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.flights_repository import FlightsRepository
from app.db.repositories.transfers_repository import TransfersRepository
from app.db.seed import seed_session


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()
    seed_session(db)
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def trip_data(db_session):
    return {
        "airports": AirportsRepository(db_session).list_airports(),
        "flights": FlightsRepository(db_session).list_all_mock_flights(),
        "transfers": TransfersRepository(db_session).list_transfers(),
    }
