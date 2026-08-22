#!/usr/bin/env python3
"""Generate Triplet's flightable global place catalogue from Travelpayouts data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen


BASE_URL = "https://api.travelpayouts.com/data/en"
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "app" / "data" / "flight_places.json"
COUNTRY_CATALOG = ROOT / "app" / "data" / "country_catalog.json"


def fetch(name: str, source_dir: Path | None) -> list[dict]:
    if source_dir:
        return json.loads((source_dir / f"travelpayouts-{name}.json").read_text(encoding="utf-8"))
    request = Request(f"{BASE_URL}/{name}.json", headers={"User-Agent": "Triplet place catalogue sync"})
    with urlopen(request, timeout=60) as response:
        return json.load(response)


def clean_code(value: object, length: int) -> str | None:
    code = str(value or "").strip().upper()
    return code if len(code) == length and code.isalpha() else None


def coordinates(row: dict) -> tuple[float | None, float | None]:
    value = row.get("coordinates") or {}
    try:
        return float(value["lat"]), float(value["lon"])
    except (KeyError, TypeError, ValueError):
        return None, None


def build(source_dir: Path | None = None) -> dict:
    airports = fetch("airports", source_dir)
    cities = fetch("cities", source_dir)
    provider_countries = fetch("countries", source_dir)
    canonical_countries = json.loads(COUNTRY_CATALOG.read_text(encoding="utf-8"))["countries"]
    canonical_by_code = {row["code"]: row for row in canonical_countries}
    provider_country_names = {
        row["code"].upper(): (row.get("name_translations") or {}).get("en") or row.get("name")
        for row in provider_countries
        if clean_code(row.get("code"), 2)
    }

    places: list[dict] = []
    for kind, rows in (("city", cities), ("airport", airports)):
        for row in rows:
            flightable = row.get("has_flightable_airport") if kind == "city" else row.get("flightable")
            if not flightable or (kind == "airport" and row.get("iata_type") != "airport"):
                continue
            code = clean_code(row.get("code"), 3)
            country_code = clean_code(row.get("country_code"), 2)
            if not code or not country_code:
                continue
            country = canonical_by_code.get(country_code, {})
            lat, lon = coordinates(row)
            places.append(
                {
                    "code": code,
                    "kind": kind,
                    "name": (row.get("name_translations") or {}).get("en") or row.get("name") or code,
                    "cityCode": clean_code(row.get("city_code"), 3) if kind == "airport" else code,
                    "countryCode": country_code,
                    "countryName": country.get("name") or provider_country_names.get(country_code) or country_code,
                    "continent": country.get("continent"),
                    "timezone": row.get("time_zone"),
                    "flightable": True,
                    "latitude": lat,
                    "longitude": lon,
                }
            )

    places.sort(key=lambda row: (row["code"], 0 if row["kind"] == "city" else 1, row["name"]))
    return {
        "source": "Travelpayouts static airports, cities, and countries datasets",
        "sourceUrls": [f"{BASE_URL}/{name}.json" for name in ("airports", "cities", "countries")],
        "filters": {
            "airports": "flightable=true and iata_type=airport",
            "cities": "has_flightable_airport=true",
        },
        "aliases": {"FRU": "BSZ"},
        "places": places,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-dir",
        type=Path,
        help="Read travelpayouts-airports.json, -cities.json and -countries.json locally.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    payload = build(args.source_dir)
    args.output.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['places'])} flightable places to {args.output}")


if __name__ == "__main__":
    main()
