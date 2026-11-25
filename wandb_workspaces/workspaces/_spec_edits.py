"""Apply the edits made to a loaded workspace onto the spec it was loaded from.

The SDK's public objects cover a fraction of a workspace spec. Rebuilding the
spec from them on save, as the SDK did, drops every field they do not model
and resets every field they fill with a default. Instead, a save starts from
the spec as loaded and changes only what the user changed.

`apply_edits(loaded, before, after)` takes the spec as loaded, what the SDK
rebuilds from the public objects right after loading (`before`), and what it
rebuilds at save time (`after`). Where `before` and `after` agree, the loaded
value is kept, whatever it is. Where they differ, the user made an edit, and
`after` wins at that path. Keys the SDK does not model are never in `before`
or `after`, so they pass through.

Lists of objects (sections, panels, run sets) are matched by their `__id__`
or `id`, falling back to equality and then to position, so a panel the user
moved or a section they renamed keeps the fields the SDK does not model.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

ID_KEYS = ("__id__", "id")


def apply_edits(loaded: Any, before: Any, after: Any) -> Any:
    """`loaded` with the changes between `before` and `after` applied."""
    if before == after:
        return loaded
    if (
        isinstance(loaded, dict)
        and isinstance(before, dict)
        and isinstance(after, dict)
    ):
        merged = dict(loaded)
        for key, value in after.items():
            if key not in before:
                merged[key] = value
            elif key in loaded:
                merged[key] = apply_edits(loaded[key], before[key], value)
            elif before[key] != value:
                merged[key] = value
        for key in before:
            if key not in after:
                merged.pop(key, None)
        return merged
    if (
        isinstance(loaded, list)
        and isinstance(before, list)
        and isinstance(after, list)
    ):
        return _apply_list_edits(loaded, before, after)
    return after


def _apply_list_edits(loaded: list, before: list, after: list) -> list:
    pairs = _pair_loaded(loaded, before)
    positional = len(loaded) == len(before) == len(after)
    used: Set[int] = set()
    merged = []
    for index, item in enumerate(after):
        j = _match(item, before, used)
        if j is None and positional and index not in used:
            j = index
        if j is None:
            merged.append(item)
            continue
        used.add(j)
        k = pairs[j]
        merged.append(
            apply_edits(loaded[k], before[j], item) if k is not None else item
        )
    return merged


def _pair_loaded(loaded: list, before: list) -> List[Optional[int]]:
    """For each item of `before`, the index of the item of `loaded` it was
    rebuilt from, or None. Items with the same id pair whatever their
    positions, as the rebuild may reorder a list (Hidden Panels goes last).
    When the lists have the same length, the items left over pair in order:
    the rebuild gives an id to an item that had none, so they cannot pair by
    id, and the reorder may have moved them off their index."""
    by_id: Dict[Tuple[str, str], int] = {}
    for index, item in enumerate(loaded):
        item_id = _item_id(item)
        if item_id is not None and item_id not in by_id:
            by_id[item_id] = index
    pairs: List[Optional[int]] = []
    taken: Set[int] = set()
    for item in before:
        item_id = _item_id(item)
        match: Optional[int] = by_id.get(item_id) if item_id is not None else None
        if match is not None and match in taken:
            match = None
        pairs.append(match)
        if match is not None:
            taken.add(match)
    if len(loaded) == len(before):
        free = [index for index in range(len(loaded)) if index not in taken]
        for j, match in enumerate(pairs):
            if match is None:
                pairs[j] = free.pop(0)
    return pairs


def _match(item: Any, before: list, used: Set[int]) -> Optional[int]:
    item_id = _item_id(item)
    if item_id is not None:
        for j, candidate in enumerate(before):
            if j not in used and _item_id(candidate) == item_id:
                return j
        # An id with no counterpart is new content.
        return None
    for j, candidate in enumerate(before):
        if j not in used and candidate == item:
            return j
    return None


def _item_id(item: Any) -> Optional[Tuple[str, str]]:
    if isinstance(item, dict):
        for key in ID_KEYS:
            value = item.get(key)
            if isinstance(value, str) and value:
                return (key, value)
    return None


def value_at(spec: Any, path: Tuple[Any, ...]) -> Tuple[bool, Any]:
    """`(found, value)` for `path` in `spec`. Parts that are not a key or
    index at their level, such as a union tag in a validation error's
    location, are skipped."""
    node = spec
    parts = list(path)
    for i, part in enumerate(parts):
        if _has(node, part):
            node = node[part]
        elif isinstance(part, str) and i + 1 < len(parts) and _has(node, parts[i + 1]):
            continue  # a union tag: the next part is the real key
        else:
            return False, None
    return True, node


def _has(node: Any, part: Any) -> bool:
    if isinstance(node, dict):
        return part in node
    if isinstance(node, list):
        return isinstance(part, int) and 0 <= part < len(node)
    return False


def json_path(path: Tuple[Any, ...]) -> str:
    return "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in path) or "$"


def format_paths(paths: List[Tuple[Any, ...]], limit: int = 5) -> str:
    shown = ", ".join(json_path(p) for p in paths[:limit])
    if len(paths) > limit:
        shown += f" and {len(paths) - limit} more"
    return shown
