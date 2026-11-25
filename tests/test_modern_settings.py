"""The legacy settings migration, checked against the pinned schema."""

import copy
import json

import jsonschema

from wandb_workspaces.workspaces import _modern_settings as ms

from .spec_harness import SCHEMA_DIR


def _definition(schema_name, definition):
    schema = json.loads((SCHEMA_DIR / schema_name).read_text())
    return schema["definitions"][definition]


def _top_level_write_keys():
    return set(
        _definition("viewspec.lean.schema.json", "OrganizedSettings")["properties"]
    )


def test_line_plot_keys_are_not_top_level_keys_of_the_write_contract():
    """A key in both places would be written at the top level, where the
    write contract has its own meaning for it."""
    assert not ms.LINE_PLOT_KEYS & _top_level_write_keys()


def test_every_legacy_setting_has_a_place_in_the_modern_block():
    """Each key the read contract allows in a legacy `Settings` block either
    moves under `linePlot`, is dropped, is remapped, or is a top-level key
    the write contract accepts. Anything else would be written where the
    write contract rejects it, as the app's own migration does."""
    legacy_keys = set(_definition("viewspec.schema.json", "Settings")["properties"])
    placed = (
        ms.LINE_PLOT_KEYS
        | ms.DERIVED_KEYS
        | ms.DEAD_KEYS
        | {"ignoreOutliers", "suppressLegends"}
        | _top_level_write_keys()
    )
    assert legacy_keys <= placed, sorted(legacy_keys - placed)


def test_migration_output_passes_the_write_contract():
    lean = json.loads((SCHEMA_DIR / "viewspec.lean.schema.json").read_text())
    validator = jsonschema.Draft7Validator(
        {"$ref": "#/definitions/OrganizedSettings", "definitions": lean["definitions"]}
    )
    legacy = {
        "xAxis": "_step",
        "xAxisFormat": "datetime",
        "smoothingType": "exponential",
        "smoothingWeight": 0.5,
        "smoothingActive": True,
        "ignoreOutliers": True,
        "suppressLegends": True,
        "fullFidelityMode": "min-max-last",
        "displayFullRunName": True,
        "showMinMaxOnHover": True,
        "shouldAutoGeneratePanels": False,
    }
    errors = list(validator.iter_errors(ms.organized_from_legacy(legacy)))
    assert errors == []


def test_the_current_keys_win_over_the_deprecated_ones():
    organized = ms.organized_from_legacy(
        {
            "ignoreOutliers": False,
            "excludeOutliers": "exclude-outliers",
            "suppressLegends": False,
            "showLegend": False,
        }
    )
    assert organized == {
        "linePlot": {"excludeOutliers": "exclude-outliers", "showLegend": False}
    }


def test_legacy_and_organized_round_trip():
    legacy = {
        "xAxis": "_step",
        "xAxisFormat": "datetime",
        "smoothingType": "gaussian",
        "smoothingWeight": 3,
        "ignoreOutliers": True,
        "suppressLegends": True,
        "shouldAutoGeneratePanels": False,
    }
    assert ms.legacy_from_organized(ms.organized_from_legacy(legacy)) == legacy
    assert ms.normalized_legacy(
        {"excludeOutliers": "include-outliers", "showLegend": False}
    ) == {"ignoreOutliers": False, "suppressLegends": True}


def test_seeds_are_the_app_migration_and_are_undone_where_no_edit_reached():
    spec = {
        "section": {
            "settings": {"xAxis": "_step", "smoothingActive": False},
            "workspaceSettings": {"ref": {"id": "r"}},
            "panelBankConfig": {
                "settings": {"sortAlphabetically": True},
                "sections": [
                    {"localPanelSettings": {"smoothingWeight": 2}},
                    {"sectionSettings": {"linePlot": {"xAxis": "_runtime"}}},
                ],
            },
        }
    }
    original = copy.deepcopy(spec)

    seeds = ms.seed_modern_blocks(spec)

    section = spec["section"]
    assert section["workspaceSettings"] == {
        "ref": {"id": "r"},
        "sortAlphabetically": True,
        "linePlot": {"xAxis": "_step"},
    }
    bank_sections = section["panelBankConfig"]["sections"]
    assert bank_sections[0]["sectionSettings"] == {"linePlot": {"smoothingWeight": 2}}
    assert bank_sections[1] == original["section"]["panelBankConfig"]["sections"][1]

    ms.unseed_untouched(spec, seeds)
    assert spec == original
