from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

_ALIASES: dict[str, str] = {
    "playstation 5": "ps5",
    "playstation5": "ps5",
    "ps5": "ps5",
    "playstation 4": "ps4",
    "playstation4": "ps4",
    "ps4": "ps4",
    "playstation 3": "ps3",
    "playstation3": "ps3",
    "ps3": "ps3",
    "playstation 2": "ps2",
    "ps2": "ps2",
    "playstation": "ps1",
    "ps1": "ps1",
    "psp": "psp",
    "ps vita": "vita",
    "vita": "vita",
    "xbox series x": "xsx",
    "xbox series s": "xss",
    "xbox series x/s": "xsx",
    "xbox series": "xsx",
    "xsx": "xsx",
    "xss": "xss",
    "xbox one": "xboxone",
    "xboxone": "xboxone",
    "xbox 360": "xbox360",
    "xbox360": "xbox360",
    "nintendo switch 2": "ns2",
    "switch 2": "ns2",
    "ns2": "ns2",
    "nintendo switch": "switch",
    "switch": "switch",
    "pc": "pc",
    "windows": "pc",
    "stadia": "stadia",
    "wii u": "wiiu",
    "wiiu": "wiiu",
    "wii": "wii",
    "3ds": "3ds",
    "nintendo 3ds": "3ds",
    "ds": "ds",
    "ios": "ios",
    "android": "android",
}


def normalize_platform_code(raw: str) -> str:
    compact = " ".join(raw.strip().lower().replace("_", " ").replace("-", " ").split())
    if compact in _ALIASES:
        return _ALIASES[compact]
    slug = _NON_ALNUM.sub("", compact)
    return _ALIASES.get(slug, slug or "unknown")
