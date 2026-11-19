"""Compare a workspace spec before and after a fetch-then-save.

`diff_specs` reports every JSON path a save dropped, added or changed, and
`write_errors` checks a spec against the view spec schema's write contract,
the only shape a client may save. The schema is the copy pinned in
schema/viewspec/ (see scripts/sync_schema.py).

Specs come from `tests/specs/*.json`, which are committed and hold no customer
data, and from the directory named by `SPEC_CORPUS`, which stays outside the
repo.
"""

import dataclasses
import functools
import json
import os
import pathlib
from typing import Any, Dict, Iterator, List, Optional, Tuple

import jsonschema
from deepdiff import DeepDiff

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema" / "viewspec"
SPECS_DIR = pathlib.Path(__file__).resolve().parent / "specs"
CORPUS_ENV = "SPEC_CORPUS"

Path = Tuple[Any, ...]

_DROPPED = ("dictionary_item_removed", "iterable_item_removed")
_ADDED = ("dictionary_item_added", "iterable_item_added")
_CHANGED = ("values_changed", "type_changes")


def format_path(path: Path) -> str:
    return "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in path)


@dataclasses.dataclass
class SpecDiff:
    dropped: List[Path]
    added: List[Path]
    changed: List[Path]

    @property
    def is_lossless(self) -> bool:
        """Nothing was dropped or changed. Additions are reported separately."""
        return not self.dropped and not self.changed

    def summary(self, limit: int = 20) -> str:
        lines = []
        for name in ("dropped", "changed", "added"):
            paths = getattr(self, name)
            if not paths:
                continue
            lines.append(f"{len(paths)} {name}:")
            lines += [f"  {format_path(p)}" for p in paths[:limit]]
            if len(paths) > limit:
                lines.append(f"  ... and {len(paths) - limit} more")
        return "\n".join(lines) or "no differences"


def diff_specs(loaded: Dict[str, Any], saved: Dict[str, Any]) -> SpecDiff:
    """The paths `saved` dropped, added or changed relative to `loaded`.

    A dropped or added object counts once, at its own path, not once per key
    inside it.
    """
    tree = DeepDiff(loaded, saved, view="tree", verbose_level=2)

    def paths(kinds):
        found = [
            tuple(level.path(output_format="list"))
            for kind in kinds
            for level in tree.get(kind, [])
        ]
        return sorted(found, key=lambda p: [str(x) for x in p])

    return SpecDiff(
        dropped=paths(_DROPPED), added=paths(_ADDED), changed=paths(_CHANGED)
    )


@functools.lru_cache(maxsize=None)
def _schema(name: str) -> Dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text())


@functools.lru_cache(maxsize=None)
def _write_validator(view_type: str) -> jsonschema.Draft7Validator:
    schema = _schema("viewspec.lean.schema.json")
    root = schema["x-view-types"][view_type]
    return jsonschema.Draft7Validator(
        {"$ref": f"#/definitions/{root}", "definitions": schema["definitions"]}
    )


def write_errors(
    spec: Dict[str, Any], view_type: str = "project-view"
) -> List[Tuple[str, str]]:
    """Where `spec` breaks the write contract for `view_type`, as
    (path, message) pairs. Empty when the spec may be saved."""
    errors = _write_validator(view_type).iter_errors(spec)
    return sorted(
        (format_path(tuple(e.absolute_path)) or "$", e.message) for e in errors
    )


def load_spec(path: pathlib.Path) -> Dict[str, Any]:
    """Read a spec file: either the spec itself, or a stored view row whose
    `spec` field holds the spec as a JSON string."""
    data = json.loads(path.read_text())
    if isinstance(data.get("spec"), str):
        return json.loads(data["spec"])
    return data


def committed_specs() -> List[pathlib.Path]:
    return sorted(SPECS_DIR.glob("*.json"))


def corpus_root() -> Optional[pathlib.Path]:
    root = os.environ.get(CORPUS_ENV)
    return pathlib.Path(root).expanduser() if root else None


def corpus_specs() -> List[pathlib.Path]:
    """The spec files under `SPEC_CORPUS`, or none when it is unset."""
    root = corpus_root()
    return sorted(root.rglob("*.json")) if root else []


def all_specs() -> Iterator[pathlib.Path]:
    yield from committed_specs()
    yield from corpus_specs()
