"""Small helpers about lines: their kind, their icon and the badge that is the pin of a line on the map."""

import base64
import re
from dataclasses import dataclass, replace

LINE_TYPE_MAP = {
    "1": "Normal bus",
    "2": "Normal bus",
    "3": "Normal periodic bus",
    "4": "Fast periodic bus",
    "5": "Fast bus",
    "6": "Unknown bus",
    "7": "Zone normal bus",
    "8": "Zone periodic bus",
    "9": "Special bus",
    "C": "Cemetery bus",
    "E": "Express periodic bus",
    "L": "Local suburban bus",
    "N": "Night bus",
    "Z": "Replacement line",
    "T": "Tram line",
    "M": "Metro line",
    "S": "Urban rail",
}

# A tram line is a one or two digit number; the buses have three digits (or letters), so this tells them apart everywhere.
TRAM_LINE = re.compile(r"[1-9]\d?")


def get_line_type(line: str) -> str:
    """Return human-friendly type of a Warsaw transport line."""
    if TRAM_LINE.fullmatch(line):
        return "Tram line"
    if re.fullmatch(r"M\d", line, re.IGNORECASE):
        return "Metro line"
    if re.fullmatch(r"S\d{1,2}", line, re.IGNORECASE):
        return "Urban rail"
    return LINE_TYPE_MAP.get(line[0].upper(), "unknown")

def get_line_icon(line: str) -> str:
    """Return appropriate MDI icon name for given line type (a bus unless it is a tram, a train or a metro)."""
    if TRAM_LINE.fullmatch(line):
        return "mdi:tram"
    if re.match(r"^S\d{1,2}$", line):
        return "mdi:train"
    if re.match(r"^M\d$", line):
        return "mdi:train-variant"
    return "mdi:bus"


@dataclass(frozen=True)
class BadgeStyle:
    """How the badge of one class of line looks: its colours and whether the line is a periodic one. Every badge is a circle:
    Home Assistant crops a picture of an entity to a circle, so a square or a rounded rectangle lost its corners."""

    fill: str
    text: str = "#ffffff"
    ring: str = "#ffffff"
    dashed: bool = False  # a dashed ring: a periodic line (3xx, 4xx, 8xx, E-x)


# The colour is the class of the line, as the City sets them apart on its posts and timetables: a dark number with a purple
# band for an ordinary line, a red number for a fast one, white digits on blue for a night one. Where the City shows no colour
# (zone, special, local, replacement lines) the colours are only a way to tell the classes apart.
_ORDINARY = BadgeStyle(fill="#f3ecfa", text="#23282f", ring="#a23db5")
_STYLES = {
    "ordinary": _ORDINARY,
    "periodic": replace(_ORDINARY, dashed=True),  # 3xx
    "fast": BadgeStyle(fill="#d93025"),  # 5xx
    "fast periodic": BadgeStyle(fill="#d93025", dashed=True),  # 4xx
    "zone": BadgeStyle(fill="#558b2f"),  # 7xx
    "zone periodic": BadgeStyle(fill="#558b2f", dashed=True),  # 8xx
    "special": BadgeStyle(fill="#607d8b"),  # 9xx, the replacement lines Z, the cemetery lines C
    "night": BadgeStyle(fill="#34479a"),
    "express": BadgeStyle(fill="#e64a19", dashed=True),  # E-x
    "local": BadgeStyle(fill="#00838f"),  # L-x
    "tram": BadgeStyle(fill="#ffe9a8", text="#2b2f36", ring="#f2a900"),
    "metro": BadgeStyle(fill="#6a1b9a"),
    "rail": BadgeStyle(fill="#2e7d32"),
}
_SERIES = {"1": "ordinary", "2": "ordinary", "3": "periodic", "4": "fast periodic", "5": "fast", "7": "zone", "8": "zone periodic", "9": "special"}
_LETTERS = {"N": "night", "E": "express", "L": "local", "Z": "special", "C": "special"}


def get_line_class(line: str) -> str:
    """The class of a line, the key of ``_STYLES``: by its letters (N, E, L, Z, C, M1, S3), by being a one or two digit tram line,
    or by the first digit of a bus line (the series 1xx to 9xx). A line that fits none of these is an ordinary one."""
    code = line.upper()
    if re.fullmatch(r"M\d", code):
        return "metro"
    if re.fullmatch(r"S\d{1,2}", code):
        return "rail"
    if TRAM_LINE.fullmatch(code):
        return "tram"
    return _LETTERS.get(code[:1]) or _SERIES.get(code[:1], "ordinary")


def get_line_badge(line: str) -> str | None:
    """A small badge with the line number as a data URI, for the pin on the map card (which draws the first letters of the
    entity's name, such as "L1M", unless the entity has a picture). The colour is the class of the line (see ``BadgeStyle``);
    the badge is always a circle. None for a line that is not a plain number or code, so nothing from the configuration is
    written into the image unchecked."""
    if not re.fullmatch(r"[0-9A-Za-z-]{1,4}", line):
        return None
    style = _STYLES[get_line_class(line)]
    code = line.upper()
    size = {1: 26, 2: 22, 3: 17}.get(len(code), 13)
    stroke = f'stroke="{style.ring}" stroke-width="3"' + (' stroke-dasharray="5 3"' if style.dashed else "")
    body = f'<circle cx="24" cy="24" r="22" fill="{style.fill}" {stroke}/>'
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        f"{body}"
        f'<text x="24" y="25" fill="{style.text}" font-family="Arial,sans-serif" font-weight="700" font-size="{size}" '
        f'text-anchor="middle" dominant-baseline="central">{code}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def get_stop_badge(pole: str) -> str | None:
    """The badge of a stop pole as a data URI, the pin of the stop on the map card: a sign with the number of the pole on a post, in a
    navy circle (a circle, because Home Assistant crops a picture of an entity to one). It is told apart from the badge of a line, which
    is a colour with the number of the line. None for a pole that is not one or two digits, so nothing unchecked is written into the image."""
    if not re.fullmatch(r"\d{1,2}", pole):
        return None
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        '<circle cx="24" cy="24" r="22" fill="#1d3557" stroke="#ffffff" stroke-width="3"/>'
        '<rect x="9" y="7" width="30" height="20" rx="3" fill="#ffd54f"/>'
        f'<text x="24" y="17.5" fill="#1d3557" font-family="Arial,sans-serif" font-weight="800" font-size="15" text-anchor="middle" dominant-baseline="central">{pole}</text>'
        '<rect x="22.4" y="27" width="3.2" height="12" fill="#ffffff"/>'
        '<rect x="16" y="38.5" width="16" height="2.6" rx="1.3" fill="#ffffff"/>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
