import json
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, unquote

RUN_COLOR_GROUP_KEY_PREFIX = "run-color-group:"
URI_COMPONENT_SAFE_CHARS = "-_.!~*'()"


class GroupPath:
    """Hierarchical grouped-run path used as a group_colors key."""

    __slots__ = ("segments",)

    def __init__(self, *segments: str):
        self.segments = tuple(segments)

    def __iter__(self):
        return iter(self.segments)

    def __len__(self):
        return len(self.segments)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GroupPath):
            return False
        return self.segments == other.segments

    def __hash__(self) -> int:
        return hash(self.segments)

    def __repr__(self) -> str:
        args = ", ".join(repr(segment) for segment in self.segments)
        return f"GroupPath({args})"


def _encode_json_uri_component(value: Any) -> str:
    return quote(
        json.dumps(value, separators=(",", ":"), ensure_ascii=False),
        safe=URI_COMPONENT_SAFE_CHARS,
    )


def _decode_json_uri_component(value: str) -> Any:
    return json.loads(unquote(value))


def build_run_color_group_key(
    runset_id: Optional[str], path: List[Dict[str, Optional[str]]]
) -> str:
    return (
        f"{RUN_COLOR_GROUP_KEY_PREFIX}"
        f"{_encode_json_uri_component(runset_id)}:"
        f"{_encode_json_uri_component(path)}"
    )


def parse_run_color_group_key(key: str) -> Optional[Dict[str, Any]]:
    if not key.startswith(RUN_COLOR_GROUP_KEY_PREFIX):
        return None

    encoded_parts = key[len(RUN_COLOR_GROUP_KEY_PREFIX) :]
    separator_index = encoded_parts.find(":")
    if separator_index == -1:
        return None

    try:
        runset_id = _decode_json_uri_component(encoded_parts[:separator_index])
        path = _decode_json_uri_component(encoded_parts[separator_index + 1 :])
    except Exception:
        return None

    if not (isinstance(runset_id, str) or runset_id is None):
        return None
    if not isinstance(path, list):
        return None

    for entry in path:
        if not isinstance(entry, dict):
            return None
        if entry.get("kind") != "group":
            return None
        if not isinstance(entry.get("key"), str):
            return None
        value = entry.get("value")
        if not (isinstance(value, str) or value is None):
            return None

    return {"runset_id": runset_id, "path": path}


def group_path_key_from_segments(segments: Tuple[str, ...]) -> object:
    if len(segments) == 1:
        return segments[0]
    return GroupPath(*segments)
