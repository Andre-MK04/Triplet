"""Seed the scheduled-service airport directory from OurAirports.

Usage:
    python -m app.data_import.import_airports [path/to/airports.csv]

Without a path it downloads airports.csv (~9 MB) from OurAirports. Idempotent:
upserts on the OurAirports id. Scope: European airports with an IATA code that
are large/medium, or small WITH scheduled service — no heliports, no closed
fields, no private strips. Widen the continent filter to expand worldwide.

Data: OurAirports (https://ourairports.com/data/), public domain.
"""

import csv
import io
import sys

import httpx

from app.data.countries import country_name
from app.database import SessionLocal
from app.db.models import AirportDirectoryDB

OURAIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
BATCH_SIZE = 500


def load_rows(path: str | None) -> list[dict]:
    if path:
        with open(path, encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    print(f"Downloading {OURAIRPORTS_URL} …")
    response = httpx.get(OURAIRPORTS_URL, timeout=120, follow_redirects=True)
    response.raise_for_status()
    return list(csv.DictReader(io.StringIO(response.text)))


def wanted(row: dict) -> bool:
    if row.get("continent") != "EU":
        return False
    iata = (row.get("iata_code") or "").strip()
    if len(iata) != 3 or not iata.isalpha():
        return False
    airport_type = row.get("type") or ""
    scheduled = (row.get("scheduled_service") or "").strip() == "yes"
    if airport_type in {"large_airport", "medium_airport"}:
        return True
    return airport_type == "small_airport" and scheduled


def run_import(path: str | None = None) -> int:
    rows = load_rows(path)
    db = SessionLocal()
    existing_ids = {row_id for (row_id,) in db.query(AirportDirectoryDB.id).all()}
    existing_iata = {
        code: row_id for (row_id, code) in db.query(AirportDirectoryDB.id, AirportDirectoryDB.iata_code).all()
    }
    seen_iata: set[str] = set()
    imported = 0
    pending = 0

    for row in rows:
        if not wanted(row):
            continue
        iata = row["iata_code"].strip().upper()
        if iata in seen_iata:
            continue  # a handful of dataset duplicates; keep the first (larger types sort first upstream)
        seen_iata.add(iata)

        values = {
            "iata_code": iata,
            "icao_code": (row.get("icao_code") or row.get("gps_code") or "").strip()[:4] or None,
            "name": (row.get("name") or iata)[:200],
            "city": ((row.get("municipality") or "").strip() or None) and row["municipality"].strip()[:160],
            "country_code": row.get("iso_country") or "",
            "country_name": country_name(row.get("iso_country") or ""),
            "latitude": float(row["latitude_deg"]),
            "longitude": float(row["longitude_deg"]),
            "type": row.get("type") or "unknown",
            "scheduled_service": (row.get("scheduled_service") or "").strip() == "yes",
            "is_active": (row.get("type") or "") != "closed",
            "source": "ourairports",
        }
        row_id = int(row["id"])
        if row_id in existing_ids:
            db.query(AirportDirectoryDB).filter(AirportDirectoryDB.id == row_id).update(values)
        elif iata in existing_iata:
            # Same airport under a different dataset id: update by IATA so we
            # never trip the unique constraint.
            db.query(AirportDirectoryDB).filter(AirportDirectoryDB.iata_code == iata).update(values)
        else:
            db.add(AirportDirectoryDB(id=row_id, **values))
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
    print(f"Imported/updated {count} European airports.")
