import unicodedata
from typing import Any, Dict
from urllib.parse import urlparse

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


def validate_url(url: str) -> str:
    parsed_url = urlparse(url)

    # Supported paths
    path = parsed_url.path
    _, entity, project, *other = path.split("/")
    if len(other) == 0:
        pass
    elif len(other) == 1 and other[0] in {"workspace", "table"}:
        pass
    else:
        raise UnsupportedViewError(
            r"Please use a saved view that looks like https://wandb.ai/{entity}/{project}?nw=a0b1c2d3"
        )

    return url
