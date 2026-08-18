from collections import Counter
from datetime import date
import re
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.data.country_catalog import Country, country_catalog, get_country
from app.db.models import CountryVisitDB, TripSuggestionDB, UserCountryDB, UserDB
from app.travel_map.schemas import (
    BulkCountryUpdate,
    ContinentProgress,
    CountryStateUpdate,
    TravelMapCountryResponse,
    TravelMapResponse,
    TravelMapStats,
    VisitResponse,
    VisitWriteRequest,
)


class TravelMapValidationError(ValueError):
    pass


class TravelMapConflictError(ValueError):
    pass


class TravelMapNotFoundError(ValueError):
    pass


class TravelMapService:
    def __init__(self, db: Session, user: UserDB):
        self.db = db
        self.user = user

    def get_map(self) -> TravelMapResponse:
        rows = list(
            self.db.scalars(
                select(UserCountryDB)
                .where(UserCountryDB.user_id == self.user.id)
                .options(selectinload(UserCountryDB.visits))
                .order_by(UserCountryDB.country_code)
            ).all()
        )
        countries = [self._country_response(row) for row in rows if self._is_meaningful(row)]
        updated_at = max((country.updatedAt for country in countries), default=None)
        return TravelMapResponse(countries=countries, stats=self._stats(countries), updatedAt=updated_at)

    def update_country(self, code: str, request: CountryStateUpdate) -> TravelMapCountryResponse:
        country = self._require_country(code)
        row = self._get_or_create(country.code)
        visit_kinds = {visit.kind for visit in row.visits}
        if request.visited is False and visit_kinds:
            raise TravelMapConflictError("Remove this country's visit records before marking it unvisited.")
        if request.lived is False and "lived" in visit_kinds:
            raise TravelMapConflictError("Remove lived-here records before clearing lived status.")

        if request.visited is not None:
            row.visited = request.visited
            if not request.visited:
                row.lived = False
        if request.lived is not None:
            row.lived = request.lived
            if request.lived:
                row.visited = True
                row.wishlist = False
        if request.wishlist is not None:
            row.wishlist = request.wishlist
        if request.visited is True:
            row.wishlist = False

        self.db.commit()
        self.db.refresh(row)
        return self._country_response(self._reload(row.id))

    def bulk_update(self, request: BulkCountryUpdate) -> TravelMapResponse:
        codes = list(dict.fromkeys(code.strip().upper() for code in request.countryCodes))
        for code in codes:
            self._require_country(code)
        for code in codes:
            row = self._get_or_create(code)
            setattr(row, request.status, request.enabled)
            if request.enabled and request.status in {"visited", "lived"}:
                row.visited = True
                row.wishlist = False
        self.db.commit()
        return self.get_map()

    def add_visit(self, code: str, request: VisitWriteRequest) -> VisitResponse:
        country = self._require_country(code)
        row = self._get_or_create(country.code)
        values = self._visit_values(request)
        duplicate = self.db.scalar(
            select(CountryVisitDB).where(
                CountryVisitDB.user_id == self.user.id,
                CountryVisitDB.country_code == country.code,
                CountryVisitDB.kind == values["kind"],
                CountryVisitDB.start_date == values["start_date"],
                CountryVisitDB.start_precision == values["start_precision"],
                CountryVisitDB.end_date == values["end_date"],
                CountryVisitDB.end_precision == values["end_precision"],
            )
        )
        if duplicate:
            raise TravelMapConflictError("That visit is already recorded.")

        visit = CountryVisitDB(
            id=str(uuid4()),
            user_id=self.user.id,
            user_country_id=row.id,
            country_code=country.code,
            **values,
        )
        self.db.add(visit)
        row.visited = True
        row.wishlist = False
        if visit.kind == "lived":
            row.lived = True
        self.db.commit()
        self.db.refresh(visit)
        return self._visit_response(visit)

    def update_visit(self, visit_id: str, request: VisitWriteRequest) -> VisitResponse:
        visit = self._require_visit(visit_id)
        values = self._visit_values(request)
        for key, value in values.items():
            setattr(visit, key, value)
        relationship = self.db.get(UserCountryDB, visit.user_country_id)
        if relationship:
            relationship.visited = True
            relationship.wishlist = False
            if visit.kind == "lived":
                relationship.lived = True
        self.db.commit()
        self.db.refresh(visit)
        return self._visit_response(visit)

    def delete_visit(self, visit_id: str) -> None:
        visit = self._require_visit(visit_id)
        self.db.delete(visit)
        # Country-level facts are deliberately preserved. Removing a dated
        # memory must not silently mark the country unvisited or not-lived.
        self.db.commit()

    def compact_ai_context(self) -> dict[str, list[str]]:
        travel_map = self.get_map()
        return {
            "visitedCountries": sorted(country.code for country in travel_map.countries if country.visited),
            "livedCountries": sorted(country.code for country in travel_map.countries if country.lived),
            "wishlistCountries": sorted(country.code for country in travel_map.countries if country.wishlist),
        }

    def _get_or_create(self, code: str) -> UserCountryDB:
        row = self.db.scalar(
            select(UserCountryDB)
            .where(UserCountryDB.user_id == self.user.id, UserCountryDB.country_code == code)
            .options(selectinload(UserCountryDB.visits))
        )
        if row:
            return row
        row = UserCountryDB(id=str(uuid4()), user_id=self.user.id, country_code=code)
        self.db.add(row)
        self.db.flush()
        return row

    def _reload(self, row_id: str) -> UserCountryDB:
        return self.db.scalar(
            select(UserCountryDB).where(UserCountryDB.id == row_id).options(selectinload(UserCountryDB.visits))
        )

    def _require_country(self, code: str) -> Country:
        country = get_country(code)
        if not country:
            raise TravelMapValidationError("Unknown Triplet country code.")
        return country

    def _require_visit(self, visit_id: str) -> CountryVisitDB:
        visit = self.db.scalar(
            select(CountryVisitDB).where(
                CountryVisitDB.id == visit_id,
                CountryVisitDB.user_id == self.user.id,
            )
        )
        if not visit:
            raise TravelMapNotFoundError("Visit not found.")
        return visit

    def _visit_values(self, request: VisitWriteRequest) -> dict:
        start_date, start_precision = parse_partial_date(request.startDate)
        end_date, end_precision = parse_partial_date(request.endDate)
        if end_date and not start_date:
            raise TravelMapValidationError("An end date requires a start date.")
        if start_date and end_date and end_date < start_date:
            raise TravelMapValidationError("Visit end date cannot be before its start date.")
        if request.tripId:
            trip = self.db.get(TripSuggestionDB, request.tripId)
            if not trip or trip.user_id != self.user.id:
                raise TravelMapValidationError("Associated trip was not found for this account.")
        return {
            "kind": request.kind,
            "start_date": start_date,
            "start_precision": start_precision,
            "end_date": end_date,
            "end_precision": end_precision,
            "note": request.note.strip() if request.note and request.note.strip() else None,
            "trip_suggestion_id": request.tripId,
        }

    def _country_response(self, row: UserCountryDB) -> TravelMapCountryResponse:
        country = self._require_country(row.country_code)
        visits = sorted(row.visits, key=lambda visit: (visit.start_date or date.min, visit.created_at), reverse=True)
        lived_from_records = any(visit.kind == "lived" for visit in visits)
        visited_from_records = bool(visits)
        lived = bool(row.lived or lived_from_records)
        visited = bool(row.visited or lived or visited_from_records)
        if lived:
            primary = "lived"
        elif visited:
            primary = "visited"
        elif row.wishlist:
            primary = "wishlist"
        else:
            primary = "unvisited"
        return TravelMapCountryResponse(
            code=country.code,
            name=country.name,
            continent=country.continent,
            visited=visited,
            lived=lived,
            wishlist=row.wishlist,
            primaryStatus=primary,
            visitCount=len([visit for visit in visits if visit.kind == "visit"]),
            residenceCount=len([visit for visit in visits if visit.kind == "lived"]),
            visits=[self._visit_response(visit) for visit in visits],
            updatedAt=row.updated_at,
        )

    def _visit_response(self, visit: CountryVisitDB) -> VisitResponse:
        return VisitResponse(
            id=visit.id,
            countryCode=visit.country_code,
            kind=visit.kind,
            startDate=format_partial_date(visit.start_date, visit.start_precision),
            endDate=format_partial_date(visit.end_date, visit.end_precision),
            startPrecision=visit.start_precision,
            endPrecision=visit.end_precision,
            note=visit.note,
            tripId=visit.trip_suggestion_id,
            createdAt=visit.created_at,
            updatedAt=visit.updated_at,
        )

    def _stats(self, countries: list[TravelMapCountryResponse]) -> TravelMapStats:
        catalog = country_catalog()
        visited = [country for country in countries if country.visited]
        visited_counts = Counter(country.continent for country in visited)
        totals = Counter(country.continent for country in catalog.counted_countries)
        progress = [
            ContinentProgress(name=continent, visited=visited_counts[continent], total=totals[continent])
            for continent in catalog.continents
        ]
        countries_visited = len(visited)
        return TravelMapStats(
            countriesVisited=countries_visited,
            countriesLivedIn=len([country for country in countries if country.lived]),
            wishlistCountries=len([country for country in countries if country.wishlist]),
            worldTotal=catalog.world_total,
            worldExploredPercentage=round((countries_visited / catalog.world_total) * 100, 1),
            continentsVisited=len([item for item in progress if item.visited > 0]),
            continentTotal=len(catalog.continents),
            continentProgress=progress,
        )

    @staticmethod
    def _is_meaningful(row: UserCountryDB) -> bool:
        return bool(row.visited or row.lived or row.wishlist or row.visits)


def parse_partial_date(value: str | None) -> tuple[date | None, str]:
    if value is None or not value.strip():
        return None, "unknown"
    value = value.strip()
    try:
        if re.fullmatch(r"\d{4}", value):
            return date(int(value), 1, 1), "year"
        if re.fullmatch(r"\d{4}-\d{2}", value):
            year, month = (int(part) for part in value.split("-"))
            return date(year, month, 1), "month"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value), "exact"
    except ValueError as exc:
        raise TravelMapValidationError("Travel dates must be real calendar dates.") from exc
    raise TravelMapValidationError("Travel dates must use YYYY, YYYY-MM, or YYYY-MM-DD.")


def format_partial_date(value: date | None, precision: str) -> str | None:
    if value is None or precision == "unknown":
        return None
    if precision == "year":
        return f"{value.year:04d}"
    if precision == "month":
        return f"{value.year:04d}-{value.month:02d}"
    return value.isoformat()
