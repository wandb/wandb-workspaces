"""Slug helpers for building W&B app URLs."""

import re

_NON_SLUG_CHAR = re.compile(r"[^A-Za-z0-9_]")
_REPEATED_DASH = re.compile(r"-+")


def slugify_title(title: str) -> str:
    """Convert a report title into the slug the W&B app builds for the same report.

    The app maps every character outside ``[A-Za-z0-9_]`` to a dash and collapses
    runs of dashes (``makeNameAndID`` in the frontend). Keeping this identical
    matters because the slug is only decoration — the report is resolved from the
    ``--<id>`` suffix — while a slug carrying percent escapes can break the app:
    react-router decodes the pathname and throws on an escape it cannot decode,
    which a truncated link (streamed text, a copy-paste cut short) easily
    produces. An ASCII slug has nothing to escape.

    Note ``re`` is Unicode-aware, so ``\\W`` here would keep CJK characters as
    word characters and leave them to be percent-encoded; the explicit ASCII
    class above does not.
    """
    return _REPEATED_DASH.sub("-", _NON_SLUG_CHAR.sub("-", title))
