import base64
import re

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


# Colour of the badge by the kind of line (the same split as the icon, plus the night lines).
_BADGE_COLOURS = {
    "mdi:tram": "#1565c0",
    "mdi:train": "#2e7d32",
    "mdi:train-variant": "#6a1b9a",
    "mdi:bus": "#c62828",
}
_NIGHT_COLOUR = "#263238"


def get_line_badge(line: str) -> str | None:
    """A small round badge with the line number as a data URI, for the pin on the map card (which draws the first
    letters of the entity's name, such as "L1M", unless the entity has a picture). None for a line that is not
    a plain number or code, so nothing from the configuration is written into the image unchecked."""
    if not re.fullmatch(r"[0-9A-Za-z-]{1,4}", line):
        return None
    colour = _NIGHT_COLOUR if line[0].upper() == "N" else _BADGE_COLOURS[get_line_icon(line.upper())]
    size = {1: 26, 2: 22, 3: 17}.get(len(line), 13)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        f'<circle cx="24" cy="24" r="22" fill="{colour}" stroke="#fff" stroke-width="2"/>'
        f'<text x="24" y="24" fill="#fff" font-family="Arial,sans-serif" font-weight="700" font-size="{size}" '
        f'text-anchor="middle" dominant-baseline="central">{line.upper()}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
