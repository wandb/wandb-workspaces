import unicodedata
from typing import Any, Dict, NamedTuple
from urllib.parse import parse_qs, urlparse

from wandb_workspaces.workspaces.errors import SpecVersionError, UnsupportedViewError


def validate_no_emoji(s: str) -> str:
    for char in s:
        if unicodedata.category(char).startswith(("So", "Sk", "Sm", "Sc", "Cs")):
            raise ValueError("Emojis are not allowed :(")
    return s


def validate_spec_version(
    spec: Dict[str, Any], *, expected_version: int
) -> Dict[str, Any]:
    actual_version = spec.get("version", -1)

    if actual_version < expected_version:
        raise SpecVersionError(
            f"Workspace {actual_version=} < {expected_version=}, please visit the workspace in the web app to upgrade the workspace spec."
        )

    if actual_version > expected_version:
        raise SpecVersionError(
            f"Workspace {actual_version=} > {expected_version=}, please upgrade the `wandb-workspace` package to the latest version."
        )

    return spec


class ViewUrl(NamedTuple):
    entity: str
    project: str
    """The raw `nw=` query value. Empty if the URL has none."""
    nw: str


def parse_view_url(url: str, base_url: str) -> ViewUrl:
    """Validate a saved view URL and return its parts."""
    parsed_url = urlparse(url)
    parsed_base_url = urlparse(base_url)

    # If `base_url` has a path, trim that from the `url`
    path = parsed_url.path
    base_path = parsed_base_url.path.rstrip("/")
    if path.startswith(base_path + "/"):
        path = path[len(base_path):]

    # Supported paths
    _, entity, project, *other = path.split("/")
    if len(other) == 0:
        pass
    elif len(other) == 1 and other[0] in {"workspace", "table"}:
        pass
    else:
        raise UnsupportedViewError(
            f"Please use a saved view that looks like {base_url.rstrip('/')}/{{entity}}/{{project}}?nw=a0b1c2d3"
        )

    # Supported NW query params
    nw = parse_qs(parsed_url.query).get("nw", [""])[0]
    if nw.startswith("nwuser"):
        raise UnsupportedViewError(
            f"Workspace API does not currently support user views. Please use a saved view that looks like {base_url.rstrip('/')}/{{entity}}/{{project}}?nw=a0b1c2d3"
        )

    return ViewUrl(entity=entity, project=project, nw=nw)
