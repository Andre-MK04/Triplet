import argparse
import json
from datetime import date

from app.routers.providers import run_skyscanner_smoke_test


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a sanitized Skyscanner live-price smoke test.")
    parser.add_argument("--origin", default="VIE", help="Origin IATA code, for example VIE.")
    parser.add_argument("--destination", default="ALC", help="Destination IATA code, for example ALC.")
    parser.add_argument("--date", default="2026-08-15", help="Departure date in YYYY-MM-DD format.")
    parser.add_argument("--max-results", type=int, default=3, help="Maximum result hint for diagnostics.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_skyscanner_smoke_test(
        origin=args.origin,
        destination=args.destination,
        departure_date=date.fromisoformat(args.date),
        max_results=max(1, min(args.max_results, 10)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
