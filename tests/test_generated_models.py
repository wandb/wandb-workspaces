"""The models generated from the view spec schema, on their own.

These check the models, not the SDK: the read model loads a spec and dumps it
back unchanged, keeping keys the schema does not declare, and the write model
accepts a spec the app would save and rejects undeclared keys. The SDK does
not use these models yet.
"""

import copy
import importlib.util
import subprocess
import sys

import pytest
from pydantic import ValidationError

from wandb_workspaces._viewspec import read, write

from .spec_harness import REPO_ROOT, committed_specs, diff_specs, load_spec

READ_ROOT = read.ProjectPageViewSpec
WRITE_ROOT = write.MultiRunWorkspaceViewSpec

SPECS = [pytest.param(p, id=p.stem) for p in committed_specs()]


def _read_dump(spec):
    model = READ_ROOT.model_validate(spec)
    return model.model_dump(mode="json", by_alias=True, exclude_unset=True)


@pytest.mark.skipif(
    importlib.util.find_spec("datamodel_code_generator") is None,
    reason="the generator needs Python 3.11 or newer",
)
def test_committed_models_match_the_schema():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate_models.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("path", SPECS)
def test_read_model_dumps_a_spec_unchanged(path):
    spec = load_spec(path)
    diff = diff_specs(spec, _read_dump(copy.deepcopy(spec)))
    assert diff.is_lossless and not diff.added, diff.summary()


@pytest.mark.parametrize("path", SPECS)
def test_write_model_accepts_a_spec_the_app_would_save(path):
    WRITE_ROOT.model_validate(load_spec(path))


def test_read_model_keeps_keys_the_schema_does_not_declare():
    spec = load_spec(committed_specs()[0])
    spec["notInTheSchema"] = {"kept": True}
    spec["section"]["alsoNotInTheSchema"] = [1, 2]

    dumped = _read_dump(spec)

    assert dumped["notInTheSchema"] == {"kept": True}
    assert dumped["section"]["alsoNotInTheSchema"] == [1, 2]


def test_read_model_keeps_legacy_keys_the_write_model_rejects():
    spec = load_spec(committed_specs()[0])
    spec["vizExpanded"] = False
    spec["section"]["settings"] = {"ignoreOutliers": True}

    dumped = _read_dump(spec)

    assert dumped["vizExpanded"] is False
    with pytest.raises(ValidationError) as raised:
        WRITE_ROOT.model_validate(dumped)
    rejected = {err["loc"] for err in raised.value.errors()}
    assert ("vizExpanded",) in rejected
    assert ("section", "settings", "ignoreOutliers") in rejected


def test_write_model_rejects_a_key_the_schema_does_not_declare():
    spec = load_spec(committed_specs()[0])
    spec["section"]["notInTheSchema"] = 1

    with pytest.raises(ValidationError) as raised:
        WRITE_ROOT.model_validate(spec)
    [err] = raised.value.errors()
    assert err["type"] == "extra_forbidden"
    assert err["loc"] == ("section", "notInTheSchema")


def test_whole_numbers_stay_integers():
    """The schema types every number as `number`; a stored 20 must not come
    back as 20.0."""
    spec = load_spec(committed_specs()[0])
    spec["section"]["runSets"][0]["runFeed"]["pageSize"] = 20
    spec["section"]["runSets"][0]["runFeed"]["columnWidths"] = {"run:name": 1.5}

    run_feed = _read_dump(spec)["section"]["runSets"][0]["runFeed"]

    assert isinstance(run_feed["pageSize"], int)
    assert run_feed["columnWidths"] == {"run:name": 1.5}


def test_panels_load_as_their_panel_type():
    """Panel is a union by `viewType`; each panel loads as its own model, so
    its config is kept and checked, not dropped."""
    spec = load_spec(REPO_ROOT / "tests" / "specs" / "unmodeled-fields.json")

    model = READ_ROOT.model_validate(spec)
    [panel] = model.section.panel_bank_config.sections[0].panels

    assert isinstance(panel, read.MediaBrowserPanel)
    assert panel.config.fit_to_dimension is True
