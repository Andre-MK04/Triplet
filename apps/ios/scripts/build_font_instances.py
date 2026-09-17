"""Rebuild native font weights from the unmodified Google Fonts sources.

Requires fonttools==4.60.0. No downloads or runtime network requests.
SIL OFL notices are bundled beside the generated fonts.
"""
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = {400: "Regular", 500: "Medium", 600: "SemiBold", 700: "Bold", 800: "ExtraBold"}

for family in ("BricolageGrotesque", "HankenGrotesk", "JetBrainsMono"):
    for weight, style in WEIGHTS.items():
        source = TTFont(ROOT / "FontSources" / f"{family}.ttf")
        axes = {axis.axisTag: axis.defaultValue for axis in source["fvar"].axes}
        axes["wght"] = weight
        if "opsz" in axes:
            axes["opsz"] = 32  # Display text, regular width; same outlines/family as web.
        font = instantiateVariableFont(source, axes, inplace=True)
        names = {1: family, 2: style, 3: f"Farelin:{family}-{style}",
                 4: f"{family} {style}", 6: f"{family}-{style}", 16: family, 17: style}
        for record in font["name"].names:
            if record.nameID in names:
                record.string = names[record.nameID].encode(record.getEncoding())
        for name_id, value in names.items():
            font["name"].setName(value, name_id, 3, 1, 0x409)
        font.save(ROOT / "Farelin/Resources/Fonts" / f"{family}-{style}.ttf")
        print(f"{family}-{style}")
