"""Seed European cities/towns into `locations` from GeoNames.

Usage:
    python -m app.data_import.import_locations [path/to/cities5000.txt]

Without a path it downloads cities5000.zip (~4 MB) from GeoNames. The import is
idempotent: rows upsert on the GeoNames id, so re-running refreshes data in
place. Only countries in EUROPE_COUNTRIES are imported for now; widen that set
to expand worldwide.

Data: GeoNames (https://www.geonames.org), CC BY 4.0.
"""

import io
import sys
import zipfile

import httpx

from app.data.countries import EUROPE_COUNTRIES, country_name
from app.database import SessionLocal
from app.db.models import LocationDB

GEONAMES_URL = "https://download.geonames.org/export/dump/cities5000.zip"
# GeoNames feature codes for populated places we want (skips district/section codes).
WANTED_FEATURE_CODES = {"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC", "PPLS"}
BATCH_SIZE = 2000


def load_rows(path: str | None) -> list[str]:
    if path:
        with open(path, encoding="utf-8") as handle:
            return handle.readlines()
    print(f"Downloading {GEONAMES_URL} …")
    response = httpx.get(GEONAMES_URL, timeout=120, follow_redirects=True)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        with archive.open("cities5000.txt") as handle:
            return io.TextIOWrapper(handle, encoding="utf-8").readlines()


def run_import(path: str | None = None) -> int:
    rows = load_rows(path)
    db = SessionLocal()
    existing_ids = {row_id for (row_id,) in db.query(LocationDB.id).all()}
    imported = 0
    pending = 0

    for line in rows:
        fields = line.rstrip("\n").split("\t")
        if len(fields) < 18:
            continue
        (
            geoname_id, name, ascii_name, _alt, lat, lon,
            feature_class, feature_code, cc, *_rest
        ) = fields[:9]
        if cc not in EUROPE_COUNTRIES:
            continue
        if feature_class != "P" or feature_code not in WANTED_FEATURE_CODES:
            continue
        population = int(fields[14]) if fields[14].isdigit() else None
        timezone = fields[17] or None

        values = {
            "name": name[:200],
            "ascii_name": (ascii_name or None) and ascii_name[:200],
            "country_code": cc,
            "country_name": country_name(cc),
            "admin_region": None,
            "latitude": float(lat),
            "longitude": float(lon),
            "population": population,
            "timezone": timezone,
            "source": "geonames",
        }
        row_id = int(geoname_id)
        if row_id in existing_ids:
            db.query(LocationDB).filter(LocationDB.id == row_id).update(values)
        else:
            db.add(LocationDB(id=row_id, **values))
        imported += 1
        pending += 1
        if pending >= BATCH_SIZE:
            db.commit()
            pending = 0

    db.commit()
    db.close()
    return imported


if __name__ == "__main__":
    count = run_import(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Imported/updated {count} European locations.")
