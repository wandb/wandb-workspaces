"""Fetch-then-save regression tests for workspace specs, ported from #156.

Each test loads a stored spec through `Workspace.from_url`, optionally edits
it through the public API, saves it, and checks the spec the save sent. They
only touch JSON in and JSON out, so they hold across a change of the internal
models.

The main fixture, tests/specs/unmodeled-fields.json, is hand-built from
#156's: at each level (section, panel bank, a Media Browser panel, run set and
run feed) it sets fields the SDK has no attribute for. It passes the view spec
schema's write contract (packages/wandb-schemas in wandb/core, pinned in
schema/viewspec/), so it is a spec the app would save today. Against #156's
version, it drops the legacy `localPanelSettings` and `settings.ignoreOutliers`,
which load migrates, and fills in a selection bound's `op` and the hidden
section's `name`, `isOpen` and `panels`, which the schema requires.

Assertions from #156 on keys the schema calls stray (the root `vizExpanded`,
`libraryExpanded` and `slowWarningHiddenAt`, and `shouldAutoGeneratePanels`
under the legacy `settings`) were not ported: the write contract rejects
them, so keeping them is not frontend behavior.

A save starts from the loaded spec and applies the user's edits onto it
(wandb_workspaces/workspaces/_spec_edits.py), so every field below survives
whether or not the SDK models it. Before that change, main dropped or rewrote
31 of them.
"""

import copy
import json

import pytest

import wandb_workspaces.workspaces as ws

from .fake_view_server import fetch_then_save
from .spec_harness import SPECS_DIR, load_spec, minimal_spec, run_set

# What `_get` returns for a path the spec does not have.
MISSING = "<missing>"


def _get(spec, path):
    """The value at `path`, or MISSING, so a dropped field fails the
    assertion rather than raising KeyError."""
    node = spec
    for part in path:
        try:
            node = node[part]
        except (KeyError, IndexError, TypeError):
            return MISSING
    return node


def _as_json(value):
    """Compare as JSON so `true` and `1`, or `1` and `1.0`, differ."""
    return json.dumps(value, sort_keys=True)


# A workspace that sets fields the SDK has no attribute for. It is also in
# the spec corpus that test_spec_corpus.py runs.
LOADED_SPEC = load_spec(SPECS_DIR / "unmodeled-fields.json")


def _case(path):
    return pytest.param(path, id=".".join(map(str, path[1:])))


SECTION = ("section",)
PANEL_BANK = SECTION + ("panelBankConfig",)
PANEL_SECTION = PANEL_BANK + ("sections", 0)
MEDIA_CONFIG = PANEL_SECTION + ("panels", 0, "config")
RUNSET = SECTION + ("runSets", 0)
RUN_FEED = RUNSET + ("runFeed",)

# The paths an unedited save must send back exactly as loaded.
PRESERVED_PATHS = [
    _case(SECTION + ("version",)),
    _case(SECTION + ("openRunSet",)),
    _case(SECTION + ("openViz",)),
    _case(SECTION + ("customRunColors",)),
    _case(SECTION + ("customRunNames",)),
    _case(SECTION + ("workspaceSettings",)),
    _case(SECTION + ("semanticLegendSettings",)),
    _case(SECTION + ("panelBankSectionConfig", "__id__")),
    _case(PANEL_BANK + ("settings", "showEmptySections")),
    _case(PANEL_BANK + ("settings", "searchQuery")),
    _case(PANEL_BANK + ("panelPlacementOverrides",)),
    _case(PANEL_BANK + ("panelConfigOverrides",)),
    _case(PANEL_SECTION + ("__id__",)),
    _case(PANEL_SECTION + ("panels", 0, "__id__")),
    _case(PANEL_SECTION + ("flowConfig", "snapToColumns")),
    _case(PANEL_SECTION + ("flowConfig", "mobileColumnsPerPage")),
    _case(PANEL_SECTION + ("sorted",)),
    _case(PANEL_SECTION + ("sectionSettings",)),
    _case(MEDIA_CONFIG + ("actualSize",)),
    _case(MEDIA_CONFIG + ("fitToDimension",)),
    _case(MEDIA_CONFIG + ("pixelated",)),
    _case(MEDIA_CONFIG + ("stepIndex",)),
    _case(MEDIA_CONFIG + ("maxGalleryItems",)),
    _case(MEDIA_CONFIG + ("maxRuns",)),
    _case(MEDIA_CONFIG + ("videoPlaybackSyncEnabled",)),
    _case(RUNSET + ("name",)),
    _case(RUNSET + ("enabled",)),
    _case(RUNSET + ("search",)),
    _case(RUNSET + ("grouping",)),
    _case(RUNSET + ("sort",)),
    _case(RUNSET + ("selections", "bounds")),
    _case(RUNSET + ("expandedRowAddresses",)),
    _case(RUN_FEED + ("columnVisible",)),
    _case(RUN_FEED + ("columnPinned",)),
    _case(RUN_FEED + ("columnWidths",)),
    _case(RUN_FEED + ("columnOrder",)),
    _case(RUN_FEED + ("pageSize",)),
    _case(RUN_FEED + ("onlyShowSelected",)),
]


@pytest.fixture(scope="module")
def unedited_save():
    return fetch_then_save(copy.deepcopy(LOADED_SPEC))


@pytest.mark.parametrize("path", PRESERVED_PATHS)
def test_unedited_save_keeps_field(unedited_save, path):
    assert _as_json(_get(unedited_save, path)) == _as_json(_get(LOADED_SPEC, path))


ADDITIVE_TREE = [{"value": "group-a", "children": ["run-a", "run-b"], "skip": False}]


def test_unedited_save_keeps_additive_selection_tree():
    """With root 0 the tree lists the visible runs, grouped. A color-only run
    setting must not flatten it."""
    saved = fetch_then_save(
        minimal_spec(
            customRunColors={"run-color": "#00ff00"},
            runSets=[
                run_set(selections={"root": 0, "bounds": [], "tree": ADDITIVE_TREE})
            ],
        )
    )

    selections = saved["section"]["runSets"][0]["selections"]
    assert selections["root"] == 0
    assert selections["tree"] == ADDITIVE_TREE
    assert saved["section"]["customRunColors"] == {"run-color": "#00ff00"}


def test_enabling_a_run_adds_it_to_an_additive_selection_tree():
    """With root 0, a run the user makes visible must join the tree."""

    def enable_run_b(workspace):
        workspace.runset_settings.run_settings["run-b"] = ws.RunSettings(disabled=False)

    saved = fetch_then_save(
        minimal_spec(
            runSets=[run_set(selections={"root": 0, "bounds": [], "tree": ["run-a"]})]
        ),
        edit=enable_run_b,
    )

    selections = saved["section"]["runSets"][0]["selections"]
    assert selections["root"] == 0
    assert sorted(selections["tree"]) == ["run-a", "run-b"]


def test_disabling_a_run_removes_it_from_an_additive_selection_tree():
    """With root 0, a run the user hides must leave the tree."""

    def disable_run_a(workspace):
        workspace.runset_settings.run_settings["run-a"].disabled = True

    saved = fetch_then_save(
        minimal_spec(
            runSets=[
                run_set(
                    selections={"root": 0, "bounds": [], "tree": ["run-a", "run-b"]}
                )
            ]
        ),
        edit=disable_run_a,
    )

    assert saved["section"]["runSets"][0]["selections"]["tree"] == ["run-b"]


def test_clearing_a_run_color_removes_it():
    def clear_color(workspace):
        workspace.runset_settings.run_settings["run-a"].color = ""

    saved = fetch_then_save(
        minimal_spec(customRunColors={"run-a": "#ff0000"}), edit=clear_color
    )

    assert saved["section"]["customRunColors"] == {}


def test_changing_pinned_columns_replaces_the_pinned_order():
    def repin(workspace):
        workspace.runset_settings.pinned_columns = ["run:displayName", "summary:new"]

    saved = fetch_then_save(
        minimal_spec(
            runSets=[
                run_set(
                    runFeed={
                        "columnVisible": {"run:displayName": True, "summary:old": True},
                        "columnPinned": {"run:displayName": True, "summary:old": True},
                        "columnOrder": ["run:displayName", "summary:old"],
                        "pageSize": 50,
                    }
                )
            ]
        ),
        edit=repin,
    )

    run_feed = saved["section"]["runSets"][0]["runFeed"]
    assert run_feed["columnPinned"] == {"run:displayName": True, "summary:new": True}
    assert run_feed["columnVisible"] == {"run:displayName": True, "summary:new": True}
    assert run_feed["columnOrder"] == ["run:displayName", "summary:new"]
    # An edit next to a field the SDK does not model leaves that field alone.
    assert run_feed["pageSize"] == 50
