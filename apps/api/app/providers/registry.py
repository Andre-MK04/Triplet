from sqlalchemy.orm import Session

from app.config import settings
from app.providers.database_flight_provider import DatabaseFlightProvider
from app.providers.duffel import DuffelFlightProvider
from app.providers.flight_provider import FlightProvider, ProviderStatus
from app.providers.mock_flight_provider import MockFlightProvider
from app.providers.skyscanner import SkyscannerFlightProvider
from app.providers.travelpayouts import TravelpayoutsAviasalesProvider


class UnknownFlightProviderError(ValueError):
    pass


# Providers that call external APIs and may be used as the live half of hybrid mode.
LIVE_PROVIDER_NAMES = ("duffel", "travelpayouts", "skyscanner")
PROVIDER_NAMES = ("mock", "database", *LIVE_PROVIDER_NAMES)


def build_provider(name: str, db: Session | None = None) -> FlightProvider:
    name = name.lower()
    if name == "mock":
        return MockFlightProvider([])
    if name == "database":
        if db is None:
            raise UnknownFlightProviderError("Database flight provider requires a database session.")
        return DatabaseFlightProvider(db)
    if name == "duffel":
        return DuffelFlightProvider(db=db)
    if name == "travelpayouts":
        return TravelpayoutsAviasalesProvider(db=db)
    if name == "skyscanner":
        return SkyscannerFlightProvider(db=db)
    raise UnknownFlightProviderError(
        f"Unknown flight provider '{name}'. Valid providers: {', '.join(PROVIDER_NAMES)} or hybrid."
    )


def build_live_provider(db: Session | None = None) -> FlightProvider:
    name = settings.live_flight_provider.lower()
    if name not in LIVE_PROVIDER_NAMES:
        raise UnknownFlightProviderError(
            f"LIVE_FLIGHT_PROVIDER must be one of: {', '.join(LIVE_PROVIDER_NAMES)}; got '{name}'."
        )
    return build_provider(name, db)


def all_provider_statuses(db: Session | None = None) -> list[ProviderStatus]:
    statuses = []
    for name in PROVIDER_NAMES:
        if name == "database" and db is None:
            continue
        statuses.append(build_provider(name, db).get_provider_status())
    return statuses
