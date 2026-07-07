"""Static travel-style metadata for seeded destinations.

Keys are airport codes; values use the same style vocabulary as
UserTravelProfile.preferredTripTypes so fit scoring can match them directly.
Curated editorial data — not provider data — so no live-price honesty concerns.
"""

DESTINATION_STYLES: dict[str, list[str]] = {
    "ALC": ["beach", "food"],
    "VLC": ["beach", "food", "culture"],
    "BCN": ["culture", "food", "nightlife", "beach"],
    "MAD": ["culture", "food", "nightlife"],
    "AGP": ["beach", "nightlife"],
    "SVQ": ["culture", "food"],
    "PMI": ["beach", "nightlife"],
    "LIS": ["culture", "food"],
    "OPO": ["food", "culture"],
    "ATH": ["culture", "food"],
    "CTA": ["beach", "food", "nature"],
    "VCE": ["culture"],
    "TSF": ["culture"],
    "VIE": ["culture", "weekend_city_break"],
    "GRZ": ["culture"],
    "BUD": ["culture", "nightlife", "weekend_city_break"],
    "ZAG": ["culture", "weekend_city_break"],
    "LJU": ["culture", "nature", "weekend_city_break"],
    "TRS": ["culture", "food"],
    "CPH": ["culture", "food", "weekend_city_break"],
    "ARN": ["culture", "weekend_city_break"],
    "GOT": ["culture", "food"],
    "OSL": ["culture", "nature"],
    "BGO": ["nature"],
    "HEL": ["culture", "nature"],
}

STYLE_LABELS: dict[str, str] = {
    "beach": "Beach",
    "food": "Food",
    "culture": "Culture",
    "nature": "Nature",
    "nightlife": "Nightlife",
    "weekend_city_break": "City break",
    "cheap_adventure": "Adventure",
    "long_haul_dream": "Long-haul",
}


def destination_styles(*airport_codes: str) -> set[str]:
    styles: set[str] = set()
    for code in airport_codes:
        styles.update(DESTINATION_STYLES.get(code.upper(), []))
    return styles


def style_labels(styles: set[str], limit: int = 2) -> list[str]:
    return [STYLE_LABELS[style] for style in sorted(styles) if style in STYLE_LABELS][:limit]
