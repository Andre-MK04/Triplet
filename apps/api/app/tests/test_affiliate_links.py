"""Deep links must land on the exact trip Triplet showed.

Triplet finds the candidate; Aviasales confirms the live fare. That handoff only
works if the search that opens is the same trip, in the same currency, with the
affiliate marker intact.
"""

from datetime import date

import pytest

from app.config import settings
from app.providers.travelpayouts.affiliate_links import (
    ItinerarySegment,
    build_aviasales_itinerary_url,
)


@pytest.fixture(autouse=True)
def marker(monkeypatch):
    monkeypatch.setattr(settings, "travelpayouts_marker", "747408")
    monkeypatch.setattr(settings, "travelpayouts_currency", "EUR")


def params(url: str) -> dict[str, str]:
    from urllib.parse import parse_qs, urlparse

    return {key: value[0] for key, value in parse_qs(urlparse(url).query).items()}


def test_one_way_carries_route_date_currency_and_marker():
    url = build_aviasales_itinerary_url([ItinerarySegment("VIE", "BCN", date(2026, 10, 6))])

    fields = params(url)
    assert "/search/VIE0610BCN1?" in url
    assert fields["currency"] == "eur"
    assert fields["marker"] == "747408"


def test_return_carries_both_dates_in_order():
    url = build_aviasales_itinerary_url([
        ItinerarySegment("VIE", "BCN", date(2026, 10, 6)),
        ItinerarySegment("BCN", "VIE", date(2026, 10, 10)),
    ])

    assert "/search/VIE0610BCN10101?" in url


def test_open_jaw_keeps_the_two_different_endpoints():
    url = build_aviasales_itinerary_url([
        ItinerarySegment("BUD", "STO", date(2026, 10, 5)),
        ItinerarySegment("HEL", "BUD", date(2026, 10, 12)),
    ])

    assert "/search/BUD0510STO-HEL1210BUD1?" in url


def test_multi_city_keeps_every_hop_in_order():
    url = build_aviasales_itinerary_url([
        ItinerarySegment("VIE", "ROM", date(2026, 10, 4)),
        ItinerarySegment("ROM", "ATH", date(2026, 10, 7)),
        ItinerarySegment("ATH", "VIE", date(2026, 10, 13)),
    ])

    assert "/search/VIE0410ROM0710ATH1310VIE1?" in url


def test_compact_route_survives_transport_without_indexed_date_fields():
    url = build_aviasales_itinerary_url([
        ItinerarySegment("VIE", "BCN", date(2026, 10, 6)),
        ItinerarySegment("BCN", "VIE", date(2026, 10, 10)),
    ])

    assert "segments" not in url
    assert " " not in url


def test_a_malformed_segment_yields_no_link_rather_than_a_broken_one():
    assert build_aviasales_itinerary_url([ItinerarySegment("VIE", "VIE", date(2026, 10, 6))]) is None
    assert build_aviasales_itinerary_url([ItinerarySegment("VIENNA", "BCN", date(2026, 10, 6))]) is None
    assert build_aviasales_itinerary_url([]) is None
    assert build_aviasales_itinerary_url([
        ItinerarySegment("CPH", "ATH", "2026-10-07"),
        ItinerarySegment("ATH", "CPH", "2026-10-06"),
    ]) is None
    assert build_aviasales_itinerary_url([ItinerarySegment("V1E", "BCN", "2026-10-06")]) is None


def test_disjoint_multi_city_retains_last_home_airport_and_omits_ground_leg():
    url = build_aviasales_itinerary_url([
        ItinerarySegment("CPH", "ATH", "2026-10-07"),
        ItinerarySegment("ATH", "SKP", "2026-10-15"),
        ItinerarySegment("SOF", "CPH", "2026-11-21"),
    ])
    assert "/search/CPH0710ATH1510SKP-SOF2111CPH1?" in url


# --- Attribution does not depend on any third-party script ------------------

def test_commission_rides_on_the_url_not_on_a_tracking_script(monkeypatch):
    """The Travelpayouts Drive script was removed from the web app.

    That is only safe because attribution is carried by the `marker` parameter
    Triplet writes into the booking URL itself. If this ever stops being true,
    removing Drive would silently cost real commission — so it is asserted.
    """
    monkeypatch.setattr(settings, "travelpayouts_marker", "547063")

    url = build_aviasales_itinerary_url(
        [
            ItinerarySegment(origin="VIE", destination="BCN", departure_date="2026-10-06"),
            ItinerarySegment(origin="BCN", destination="VIE", departure_date="2026-10-10"),
        ]
    )

    assert url is not None
    assert "marker=547063" in url


def test_booking_links_are_https(monkeypatch):
    """Production affiliate links must never be downgraded to http."""
    monkeypatch.setattr(settings, "travelpayouts_marker", "547063")

    url = build_aviasales_itinerary_url(
        [ItinerarySegment(origin="VIE", destination="BCN", departure_date="2026-10-06")]
    )

    assert url is not None and url.startswith("https://")
