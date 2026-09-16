"""Refresh the bundled UN M49 world-region mapping from the official table.

Run manually: python scripts/import_un_regions.py
No network call is made during a user search. Review the diff before release.
Source: https://unstats.un.org/unsd/methodology/m49/overview
"""

from __future__ import annotations

from collections import defaultdict
from html.parser import HTMLParser
import json
from pathlib import Path
import ssl
import sys
from urllib.request import urlopen

import certifi


SOURCE = "https://unstats.un.org/unsd/methodology/m49/overview"
OUTPUT = Path(__file__).resolve().parents[1] / "app/data/un_m49_regions.json"


class TableRows(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_table = False
        self.in_body = False
        self.finished = False
        self.in_cell = False
        self.cell = ""
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table" and not self.in_table and not self.finished:
            self.in_table = True
        elif tag == "tbody" and self.in_table:
            self.in_body = True
        elif tag == "tr" and self.in_body:
            self.row = []
        elif tag == "td" and self.in_body:
            self.in_cell, self.cell = True, ""

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_cell:
            self.row.append(" ".join(self.cell.split()))
            self.in_cell = False
        elif tag == "tr" and self.in_body and len(self.row) >= 12:
            self.rows.append(self.row)
        elif tag == "tbody" and self.in_body:
            self.in_body = False
        elif tag == "table" and self.in_table:
            self.in_table = False
            self.finished = True


def main() -> None:
    parser = TableRows()
    if "--stdin" in sys.argv:
        parser.feed(sys.stdin.read())
    else:
        with urlopen(SOURCE, timeout=20,
                     context=ssl.create_default_context(cafile=certifi.where())) as response:
            parser.feed(response.read().decode("utf-8"))
    if len(parser.rows) < 200:
        raise RuntimeError(f"UN M49 table looked incomplete ({len(parser.rows)} rows); not updating file")
    regions: dict[str, set[str]] = defaultdict(set)
    for row in parser.rows:
        iso2 = row[10]
        if len(iso2) != 2 or not iso2.isalpha():
            continue
        for label in (row[3], row[5], row[7]):
            if label:
                regions[label.casefold()].add(iso2.upper())
    payload = {name: sorted(codes) for name, codes in sorted(regions.items()) if codes}
    if len(payload) < 20:
        raise RuntimeError("UN M49 region mapping looked incomplete; not updating file")
    OUTPUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Imported {len(payload)} world regions from {len(parser.rows)} UN country/area rows")


if __name__ == "__main__":
    main()
