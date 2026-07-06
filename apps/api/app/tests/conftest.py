import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.db import models  # noqa: F401
from app.db.repositories.airports_repository import AirportsRepository
from app.db.repositories.flights_repository import FlightsRepository
from app.db.repositories.transfers_repository import TransfersRepository
from app.db.seed import seed_session


@pytest.fixture(autouse=True)
def isolated_provider_settings(monkeypatch):
    """Tests must never see real credentials from a developer's .env or hit live APIs.

    Individual tests re-enable what they need via their own monkeypatch, which
    applies after this fixture and therefore wins.
    """
    monkeypatch.setattr(settings, "flight_provider", "database")
    monkeypatch.setattr(settings, "live_flight_provider", "duffel")
    monkeypatch.setattr(settings, "duffel_api_enabled", False)
    monkeypatch.setattr(settings, "duffel_api_key", None)
    monkeypatch.setattr(settings, "travelpayouts_api_enabled", False)
    monkeypatch.setattr(settings, "travelpayouts_api_token", None)
    monkeypatch.setattr(settings, "travelpayouts_marker", None)
    monkeypatch.setattr(settings, "skyscanner_api_enabled", False)
    monkeypatch.setattr(settings, "skyscanner_api_key", None)
    monkeypatch.setattr(settings, "skyscanner_media_partner_id", None)
    monkeypatch.setattr(settings, "ai_enabled", False)
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)
    monkeypatch.setattr(settings, "billing_enabled", False)
    monkeypatch.setattr(settings, "email_provider", "console")


@pytest.fixture(autouse=True)
def block_real_http(monkeypatch):
    """Fail loudly if any test reaches for the network. Tests that need HTTP
    monkeypatch httpx.get/post themselves, which overrides this guard."""

    def _blocked(*args, **kwargs):
        raise AssertionError("Tests must not make real HTTP requests. Monkeypatch httpx in the test.")

    monkeypatch.setattr(httpx, "get", _blocked)
    monkeypatch.setattr(httpx, "post", _blocked)


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
