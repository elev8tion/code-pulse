"""Intensity → Rich color gradient utilities for the heat map."""


def intensity_to_color(intensity: float) -> str:
    """
    Map 0.0–1.0 to a green gradient:
      0.0 = dim (#1a3300)
      0.5 = mid (#33aa00)
      1.0 = bright (#00ff41)
    Returns a Rich-compatible hex color string.
    """
    intensity = max(0.0, min(1.0, intensity))

    if intensity < 0.5:
        t = intensity * 2
        r = int(0x1a + (0x33 - 0x1a) * t)
        g = int(0x33 + (0xaa - 0x33) * t)
        b = int(0x00 + (0x00 - 0x00) * t)
    else:
        t = (intensity - 0.5) * 2
        r = int(0x33 + (0x00 - 0x33) * t)
        g = int(0xaa + (0xff - 0xaa) * t)
        b = int(0x00 + (0x41 - 0x00) * t)

    return f"#{r:02x}{g:02x}{b:02x}"


def intensity_bar(intensity: float, width: int = 10) -> str:
    """Return a block bar string of given width colored by intensity."""
    filled = max(1, int(intensity * width)) if intensity > 0 else 0
    return "█" * filled


def change_type_color(change_type: str) -> str:
    """Return Rich color name for a diff change type."""
    return {
        "added": "green",
        "deleted": "red",
        "modified": "yellow",
    }.get(change_type, "white")


def change_type_icon(change_type: str) -> str:
    return {
        "added": "+",
        "deleted": "-",
        "modified": "~",
    }.get(change_type, "?")
