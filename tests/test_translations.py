"""Every translation of the integration has exactly the keys of en.json and keeps the placeholders and the markup of its texts."""

from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

DIR = Path(__file__).resolve().parent.parent / "custom_components" / "ztm_warsaw" / "translations"
LANGUAGES = sorted(p.stem for p in DIR.glob("*.json") if p.stem != "en")
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def _flat(node, prefix=""):
    """Return ``{path: text}`` for every text in a translation file."""
    if isinstance(node, dict):
        return {k: v for key, child in node.items() for k, v in _flat(child, f"{prefix}{key}.").items()}
    return {prefix.rstrip("."): node}


def test_the_expected_languages_are_there():
    """English is the source; Polish and the languages foreigners in Warsaw use are translated."""
    assert {"pl", "uk", "ru", "de", "es", "fr", "it"} <= set(LANGUAGES)


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_translation_has_the_keys_of_english_and_no_more(language):
    """A missing key falls back to English in the dialog, a stray one is dead text: both mean the file is out of date."""
    english = _flat(json.loads((DIR / "en.json").read_text()))
    translated = _flat(json.loads((DIR / f"{language}.json").read_text()))
    assert set(translated) == set(english)


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_translation_keeps_the_placeholders_and_the_paragraphs(language):
    """A lost ``{line}`` or ``{portal}`` shows up in the dialog as a hole or an error; the paragraph breaks and links keep the text readable."""
    english = _flat(json.loads((DIR / "en.json").read_text()))
    translated = _flat(json.loads((DIR / f"{language}.json").read_text()))
    for path, text in english.items():
        other = translated[path]
        assert sorted(PLACEHOLDER.findall(other)) == sorted(PLACEHOLDER.findall(text)), path
        assert other.count("\n\n") == text.count("\n\n"), path
        assert other.count("](") == text.count("]("), path
