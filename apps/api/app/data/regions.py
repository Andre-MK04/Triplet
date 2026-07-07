"""Region and city vocabulary for destination parsing.

Codes must exist in the airports seed; regions use the same airport universe
the providers can actually search.
"""

REGION_TO_AIRPORTS: dict[str, list[str]] = {
    "scandinavia": ["CPH", "OSL", "BGO", "ARN", "GOT"],
    "nordics": ["CPH", "OSL", "BGO", "ARN", "GOT", "HEL"],
    "spain": ["BCN", "MAD", "VLC", "ALC", "AGP", "SVQ", "PMI"],
    "portugal": ["LIS", "OPO"],
    "greece": ["ATH"],
    "italy": ["VCE", "TSF", "TRS", "CTA"],
    "iberia": ["BCN", "MAD", "VLC", "ALC", "AGP", "SVQ", "PMI", "LIS", "OPO"],
}

# Every seeded city, usable as a destination. Origin parsing keeps its own,
# smaller list of origin-candidate cities.
CITY_TO_DESTINATION_AIRPORTS: dict[str, list[str]] = {
    "ljubljana": ["LJU"],
    "zagreb": ["ZAG"],
    "vienna": ["VIE"],
    "graz": ["GRZ"],
    "budapest": ["BUD"],
    "trieste": ["TRS"],
    "venice": ["VCE", "TSF"],
    "alicante": ["ALC"],
    "valencia": ["VLC"],
    "barcelona": ["BCN"],
    "madrid": ["MAD"],
    "malaga": ["AGP"],
    "seville": ["SVQ"],
    "palma": ["PMI"],
    "mallorca": ["PMI"],
    "lisbon": ["LIS"],
    "porto": ["OPO"],
    "athens": ["ATH"],
    "catania": ["CTA"],
    "sicily": ["CTA"],
    "copenhagen": ["CPH"],
    "stockholm": ["ARN"],
    "oslo": ["OSL"],
    "bergen": ["BGO"],
    "gothenburg": ["GOT"],
    "helsinki": ["HEL"],
}
