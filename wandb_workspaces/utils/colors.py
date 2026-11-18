"""Validate colors before they are saved, since the W&B App crashes on colors it can't parse."""

import re
from typing import Optional

_HEX = re.compile(r"#(?:[0-9a-f]{3,4}|[0-9a-f]{6}|[0-9a-f]{8})", re.I)
_NUM = r"\s*[-+]?(?:\d+\.?\d*|\.\d+)%?\s*"
_FUNC = re.compile(rf"(rgba?|hsla?)\(({_NUM}),({_NUM}),({_NUM})(?:,({_NUM}))?\)", re.I)
_NAME = re.compile(r"[a-z]+", re.I)

TRANSPARENT_ALPHA = 0.1


def is_valid_color(color: object) -> bool:
    """Return True for hex, rgb()/rgba()/hsl()/hsla() and CSS color names."""
    if not isinstance(color, str):
        return False
    color = color.strip()
    return bool(
        _HEX.fullmatch(color) or _FUNC.fullmatch(color) or _NAME.fullmatch(color)
    )


def transparent_color(color: str) -> Optional[str]:
    """Return `color` at 10% opacity, or None if it can't be derived.

    Hex colors get a `19` alpha suffix; functional colors become rgba()/hsla().
    """
    color = color.strip()
    if _HEX.fullmatch(color):
        digits = color[1:]
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits[:3])
        return f"#{digits[:6]}19"
    match = _FUNC.fullmatch(color)
    if match:
        kind = match.group(1).lower().rstrip("a")
        channels = ",".join(match.group(i).strip() for i in (2, 3, 4))
        return f"{kind}a({channels},{TRANSPARENT_ALPHA})"
    return None
