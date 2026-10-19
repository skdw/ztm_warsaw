"""The integration ships its own brand images (Home Assistant 2026.3 and newer read them from ``brand/``)."""

from __future__ import annotations

from pathlib import Path
import struct

import pytest

BRAND = Path(__file__).resolve().parent.parent / "custom_components" / "ztm_warsaw" / "brand"
SIZES = {"icon.png": (256, 256), "icon@2x.png": (512, 512), "logo.png": (256, 128), "logo@2x.png": (512, 256)}


def _size(path: Path) -> tuple[int, int]:
    """The width and height of a PNG file, read from its header (the file must be a PNG)."""
    header = path.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", header[16:24])


@pytest.mark.parametrize(("name", "size"), sorted(SIZES.items()))
def test_a_brand_image_is_a_png_of_the_size_home_assistant_expects(name, size):
    """Home Assistant wants an icon of at least 256x256 and a logo at least 128 high, and a double-size variant of each."""
    assert _size(BRAND / name) == size
