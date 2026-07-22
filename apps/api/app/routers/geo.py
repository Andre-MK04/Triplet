"""Location + airport directory search for the travel profile and search UIs."""

import math

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.db.models import AirportDirectoryDB, LocationDB

router = APIRouter(tags=["geo"])

# Rough km-per-degree bounding box factor for candidate pre-filtering.
KM_PER_DEG_LAT = 111.0


class LocationResult(BaseModel):
    id: int
    name: str
    countryCode: str
    countryName: str
    adminRegion: str | None = None
    latitude: float
    longitude: float
    population: int | None = None


class AirportResult(BaseModel):
    iataCode: str
    name: str
    city: str | None = None
    countryCode: str
    countryName: str
    latitude: float
    longitude: float
    type: str
    scheduledService: bool
    distanceKm: float | None = None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def _location_result(row: LocationDB) -> LocationResult:
    return LocationResult(
        id=row.id,
        name=row.name,
        countryCode=row.country_code,
        countryName=row.country_name,
        adminRegion=row.admin_region,
        latitude=row.latitude,
        longitude=row.longitude,
        population=row.population,
    )


def _airport_result(row: AirportDirectoryDB, distance_km: float | None = None) -> AirportResult:
    return AirportResult(
        iataCode=row.iata_code,
        name=row.name,
        city=row.city,
        countryCode=row.country_code,
        countryName=row.country_name,
        latitude=row.latitude,
        longitude=row.longitude,
        type=row.type,
        scheduledService=row.scheduled_service,
        distanceKm=round(distance_km, 1) if distance_km is not None else None,
    )


@router.get("/locations/search", response_model=list[LocationResult])
def search_locations(
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=8, ge=1, le=25),
    db: Session = Depends(get_db),
) -> list[LocationResult]:
    needle = f"{q.strip().lower()}%"
    rows = db.scalars(
        select(LocationDB)
        .where(
            or_(
                func.lower(LocationDB.name).like(needle),
                func.lower(LocationDB.ascii_name).like(needle),
            )
        )
        .order_by(LocationDB.population.desc().nulls_last(), LocationDB.name)
        .limit(limit)
    ).all()
    return [_location_result(row) for row in rows]


@router.get("/locations/{location_id}", response_model=LocationResult)
def get_location(location_id: int, db: Session = Depends(get_db)) -> LocationResult:
    row = db.get(LocationDB, location_id)
    if not row:
        raise HTTPException(status_code=404, detail="Location not found.")
    return _location_result(row)


@router.get("/airports/search", response_model=list[AirportResult])
def search_airports(
    q: str = Query(min_length=2, max_length=80),
    limit: int = Query(default=8, ge=1, le=25),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    db: Session = Depends(get_db),
) -> list[AirportResult]:
    """Search active scheduled-service airports by name, city, IATA code, or country."""
    term = q.strip().lower()
    needle = f"{term}%"
    contains = f"%{term}%"
    rows = db.scalars(
        select(AirportDirectoryDB)
        .where(AirportDirectoryDB.is_active.is_(True))
        .where(AirportDirectoryDB.scheduled_service.is_(True))
        .where(
            or_(
                func.lower(AirportDirectoryDB.iata_code) == term,
                func.lower(AirportDirectoryDB.city).like(needle),
                func.lower(AirportDirectoryDB.name).like(contains),
                func.lower(AirportDirectoryDB.country_name).like(needle),
            )
        )
        .limit(120)
    ).all()

    def rank(row: AirportDirectoryDB) -> tuple:
        exact_iata = 0 if row.iata_code.lower() == term else 1
        city_prefix = 0 if (row.city or "").lower().startswith(term) else 1
        type_rank = {"large_airport": 0, "medium_airport": 1}.get(row.type, 2)
        return (exact_iata, city_prefix, type_rank, row.name)

    rows = sorted(rows, key=rank)[:limit]
    if lat is not None and lon is not None:
        return [_airport_result(row, haversine_km(lat, lon, row.latitude, row.longitude)) for row in rows]
    return [_airport_result(row) for row in rows]


@router.get("/airports/recommended", response_model=list[AirportResult])
def recommended_airports(
    locationId: int | None = Query(default=None),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lon: float | None = Query(default=None, ge=-180, le=180),
    maxDistanceKm: float = Query(default=200, ge=10, le=1500),
    limit: int = Query(default=12, ge=1, le=30),
    db: Session = Depends(get_db),
) -> list[AirportResult]:
    """Active scheduled-service airports within maxDistanceKm of a point, nearest first."""
    if locationId is not None:
        location = db.get(LocationDB, locationId)
        if not location:
            raise HTTPException(status_code=404, detail="Location not found.")
        lat, lon = location.latitude, location.longitude
    if lat is None or lon is None:
        raise HTTPException(status_code=400, detail="Provide locationId or lat and lon.")

    # Bounding-box pre-filter, exact haversine after.
    dlat = maxDistanceKm / KM_PER_DEG_LAT
    dlon = maxDistanceKm / (KM_PER_DEG_LAT * max(0.2, math.cos(math.radians(lat))))
    candidates = db.scalars(
        select(AirportDirectoryDB)
        .where(AirportDirectoryDB.is_active.is_(True))
        .where(AirportDirectoryDB.scheduled_service.is_(True))
        .where(AirportDirectoryDB.latitude.between(lat - dlat, lat + dlat))
        .where(AirportDirectoryDB.longitude.between(lon - dlon, lon + dlon))
    ).all()

    within = []
    for row in candidates:
        distance = haversine_km(lat, lon, row.latitude, row.longitude)
        if distance <= maxDistanceKm:
            within.append((distance, row))

    # Nearest first, with a small importance boost so a big hub 20 km further
    # than a tiny field still ranks sensibly.
    type_penalty = {"large_airport": 0.0, "medium_airport": 25.0}
    within.sort(key=lambda item: item[0] + type_penalty.get(item[1].type, 60.0))
    return [_airport_result(row, distance) for distance, row in within[:limit]]


@router.get("/airports/{iata_code}", response_model=AirportResult)
def get_airport(iata_code: str, db: Session = Depends(get_db)) -> AirportResult:
    row = db.scalar(
        select(AirportDirectoryDB).where(AirportDirectoryDB.iata_code == iata_code.strip().upper())
    )
    if not row:
        raise HTTPException(status_code=404, detail="Airport not found.")
    return _airport_result(row)
