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
    """Return appropriate MDI icon name for given line type."""
    if re.fullmatch(r"[1-9]\d?", line):
        return "mdi:tram"
    elif re.match(r"^\d{3}$", line):
        return "mdi:bus"
    elif re.match(r"^N\d{2}$", line):
        return "mdi:bus"
    elif re.match(r"^L-?\d{1,2}$", line):
        return "mdi:bus"
    elif re.match(r"^S\d{1,2}$", line):
        return "mdi:train"
    elif re.match(r"^M\d$", line):
        return "mdi:train-variant"
    return "mdi:bus"