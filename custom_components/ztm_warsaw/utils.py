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

def get_line_type(line: str) -> str:
    """Return human-friendly type of a Warsaw transport line."""
    if re.fullmatch(r"[1-9]\d?", line):
        return "Tram line"
    if re.fullmatch(r"M\d", line, re.IGNORECASE):
        return "Metro line"
    if re.fullmatch(r"S\d{1,2}", line, re.IGNORECASE):
        return "Urban rail"
    return LINE_TYPE_MAP.get(line[0].upper(), "unknown")

def get_line_icon(line: str) -> str:
    """Return appropriate MDI icon name for given line type (a bus unless it is a tram, a train or a metro)."""
    if re.fullmatch(r"[1-9]\d?", line):
        return "mdi:tram"
    if re.match(r"^S\d{1,2}$", line):
        return "mdi:train"
    if re.match(r"^M\d$", line):
        return "mdi:train-variant"
    return "mdi:bus"


@dataclass(frozen=True)
class BadgeStyle:
    """How the badge of one class of line looks: its colours, its shape and whether the line is a periodic one."""

    fill: str
    text: str = "#ffffff"
    ring: str = "#ffffff"
    shape: str = "circle"  # "circle" for a bus, "rect" for a tram, "square" for the metro and the urban rail
    dashed: bool = False  # a dashed ring: a periodic line (3xx, 4xx, 8xx, E-x)
    moon: bool = False  # a night line


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
    "night": BadgeStyle(fill="#34479a", moon=True),
    "express": BadgeStyle(fill="#e64a19", dashed=True),  # E-x
    "local": BadgeStyle(fill="#00838f"),  # L-x
    "tram": BadgeStyle(fill="#ffe9a8", text="#2b2f36", ring="#f2a900", shape="rect"),
    "metro": BadgeStyle(fill="#6a1b9a", shape="square"),
    "rail": BadgeStyle(fill="#2e7d32", shape="square"),
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
    if re.fullmatch(r"[1-9]\d?", code):
        return "tram"
    return _LETTERS.get(code[:1]) or _SERIES.get(code[:1], "ordinary")


def get_line_badge(line: str) -> str | None:
    """A small badge with the line number as a data URI, for the pin on the map card (which draws the first letters of the
    entity's name, such as "L1M", unless the entity has a picture). The colour is the class of the line, the shape the kind of
    vehicle (see ``BadgeStyle``). None for a line that is not a plain number or code, so nothing from the configuration is
    written into the image unchecked."""
    if not re.fullmatch(r"[0-9A-Za-z-]{1,4}", line):
        return None
    style = _STYLES[get_line_class(line)]
    code = line.upper()
    size = {1: 26, 2: 22, 3: 17}.get(len(code), 13)
    stroke = f'stroke="{style.ring}" stroke-width="3"' + (' stroke-dasharray="5 3"' if style.dashed else "")
    if style.shape == "rect":
        body = f'<rect x="2" y="9" width="44" height="30" rx="9" fill="{style.fill}" {stroke}/>'
    elif style.shape == "square":
        body = f'<rect x="3" y="3" width="42" height="42" rx="5" fill="{style.fill}" {stroke}/>'
    else:
        body = f'<circle cx="24" cy="24" r="22" fill="{style.fill}" {stroke}/>'
    moon = '<path transform="translate(7 0) scale(.8)" d="M38 7a6 6 0 1 0 4 9a5 5 0 1 1-4-9z" fill="#ffd54f"/>' if style.moon else ""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        f"{body}{moon}"
        f'<text x="24" y="25" fill="{style.text}" font-family="Arial,sans-serif" font-weight="700" font-size="{size}" '
        f'text-anchor="middle" dominant-baseline="central">{code}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
