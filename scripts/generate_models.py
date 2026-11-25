"""Generate the view spec models from the pinned schema in schema/viewspec/.

    uv run python scripts/generate_models.py [--check]

Writes wandb_workspaces/_viewspec/read.py from the read contract and
wandb_workspaces/_viewspec/write.py from the write contract. `--check` writes
nothing and exits non-zero when the committed models are stale, which the
test suite runs so a schema sync cannot land without its models.

Before generating, it rewrites two things in the schema that
datamodel-code-generator does not translate faithfully:

- A union written as draft-07 `allOf` of `if`/`then` (Panel by `viewType`,
  Block by `type`) becomes a `oneOf` with a `discriminator`. Left as is, the
  generator emits a model with only the discriminator field, which drops
  everything else on load.
- `"type": "number"` becomes `["integer", "number"]`. The schema comes from
  TypeScript, where every number is a `number`; as a plain float, a stored
  `20` would be written back as `20.0`.
"""

import argparse
import copy
import json
import pathlib
import subprocess
import sys
import tempfile
from typing import Any, Dict

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCHEMA_DIR = ROOT / "schema" / "viewspec"
OUT_DIR = ROOT / "wandb_workspaces" / "_viewspec"

CONTRACTS = {
    "read": "viewspec.schema.json",
    "write": "viewspec.lean.schema.json",
}

HEADER = '''"""Generated from schema/viewspec/{schema} at wandb/core@{commit}.

Do not edit: run `uv run python scripts/generate_models.py`.
"""
'''

GENERATOR_ARGS = [
    "--input-file-type", "jsonschema",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.10",
    "--use-annotated",
    "--snake-case-field",
    "--use-schema-description",
    "--use-field-description",
    "--collapse-root-models",
    "--allow-population-by-field-name",
    "--disable-timestamp",
    "--formatters", "ruff-format",
]  # fmt: skip


def _discriminated_union(definition: Dict[str, Any]) -> Dict[str, Any]:
    branches = definition["allOf"]
    [prop] = {name for b in branches for name in b["if"]["properties"]}
    keep = {k: definition[k] for k in ("title", "description") if k in definition}
    return {
        **keep,
        "oneOf": [b["then"] for b in branches],
        "discriminator": {"propertyName": prop},
    }


def _is_if_then_union(definition: Dict[str, Any]) -> bool:
    branches = definition.get("allOf") or []
    return bool(branches) and all("if" in b and "then" in b for b in branches)


def _widen_numbers(node: Any) -> Any:
    if isinstance(node, dict):
        node = {k: _widen_numbers(v) for k, v in node.items()}
        if node.get("type") == "number":
            node["type"] = ["integer", "number"]
        elif isinstance(node.get("type"), list) and "number" in node["type"]:
            node["type"] = sorted(set(node["type"]) | {"integer"})
        return node
    if isinstance(node, list):
        return [_widen_numbers(v) for v in node]
    return node


def prepare(schema: Dict[str, Any]) -> Dict[str, Any]:
    schema = copy.deepcopy(schema)
    definitions = schema["definitions"]
    for name, definition in definitions.items():
        if _is_if_then_union(definition):
            definitions[name] = _discriminated_union(definition)
    return _widen_numbers(schema)


def generate(contract: str) -> str:
    schema_name = CONTRACTS[contract]
    schema = json.loads((SCHEMA_DIR / schema_name).read_text())
    commit = json.loads((SCHEMA_DIR / "SOURCE.json").read_text())["commit"]
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / schema_name
        out = pathlib.Path(tmp) / f"{contract}.py"
        src.write_text(json.dumps(prepare(schema)))
        subprocess.run(
            [
                sys.executable, "-m", "datamodel_code_generator",
                "--input", str(src), "--output", str(out), *GENERATOR_ARGS,
            ],
            check=True,
            capture_output=True,
            text=True,
        )  # fmt: skip
        body = out.read_text()
    return HEADER.format(schema=schema_name, commit=commit[:12]) + "\n" + body


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    stale = []
    for contract in CONTRACTS:
        path = OUT_DIR / f"{contract}.py"
        text = generate(contract)
        if args.check:
            if not path.exists() or path.read_text() != text:
                stale.append(path.relative_to(ROOT))
            continue
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"wrote {path.relative_to(ROOT)}")
    if stale:
        sys.exit(f"stale: {', '.join(map(str, stale))}; run scripts/generate_models.py")


if __name__ == "__main__":
    main()
