"""Check a workspace spec against the view spec schema's contracts.

The models in `wandb_workspaces._viewspec` are generated from the schema. The
read contract is what the app loads, legacy shapes included; the write
contract is the only shape a client may save. Both imports are deferred, as
the generated modules take a moment to load and most code paths never save.
"""

from typing import Any, Dict, List, Tuple

from pydantic import ValidationError

Path = Tuple[Any, ...]
ContractError = Tuple[Path, str]


def read_errors(spec: Dict[str, Any]) -> List[ContractError]:
    """Where `spec` breaks the read contract, as (path, message) pairs."""
    from wandb_workspaces._viewspec import read

    return _errors(read.ProjectPageViewSpec, spec)


def write_errors(spec: Dict[str, Any]) -> List[ContractError]:
    """Where `spec` breaks the write contract, as (path, message) pairs."""
    from wandb_workspaces._viewspec import write

    return _errors(write.MultiRunWorkspaceViewSpec, spec)


def _errors(model, spec: Dict[str, Any]) -> List[ContractError]:
    try:
        model.model_validate(spec)
    except ValidationError as e:
        return [(tuple(err["loc"]), err["msg"]) for err in e.errors()]
    return []
