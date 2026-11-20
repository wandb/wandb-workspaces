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

`xfail(strict=True)` marks a field main drops or rewrites today. When a fix
makes one pass, strict xfail fails the run until its mark is removed. Only an
AssertionError counts as the expected failure, so a crash while loading,
editing or saving still shows as an error.
"""

import copy
import json

import pytest

import wandb_workspaces.workspaces as ws

from .fake_view_server import fetch_then_save
from .spec_harness import SPECS_DIR, load_spec

DROPPED_ON_MAIN = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="main drops or rewrites this field on save",
)

# What `_get` returns for a path the spec does not have.
MISSING = "<missing>"


def _empty_section(**overrides):
    section = {
        "panelBankConfig": {"state": 1, "settings": {}, "sections": []},
        "panelBankSectionConfig": {},
        "customRunColors": {},
        "runSets": [{"id": "rs1"}],
    }
    section.update(overrides)
    return {"section": section}


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


def _case(path, *, dropped):
    return pytest.param(
        path,
        id=".".join(map(str, path[1:])),
        marks=[DROPPED_ON_MAIN] if dropped else [],
    )


SECTION = ("section",)
PANEL_BANK = SECTION + ("panelBankConfig",)
PANEL_SECTION = PANEL_BANK + ("sections", 0)
MEDIA_CONFIG = PANEL_SECTION + ("panels", 0, "config")
RUNSET = SECTION + ("runSets", 0)
RUN_FEED = RUNSET + ("runFeed",)

# The paths an unedited save must send back exactly as loaded. `dropped`
# marks the ones main drops or rewrites today.
PRESERVED_PATHS = [
    _case(SECTION + ("version",), dropped=True),
    _case(SECTION + ("openRunSet",), dropped=True),
    _case(SECTION + ("openViz",), dropped=True),
    _case(SECTION + ("customRunColors",), dropped=True),
    _case(SECTION + ("customRunNames",), dropped=True),
    _case(SECTION + ("workspaceSettings",), dropped=True),
    _case(SECTION + ("semanticLegendSettings",), dropped=True),
    _case(PANEL_BANK + ("settings", "showEmptySections"), dropped=True),
    _case(PANEL_BANK + ("settings", "searchQuery"), dropped=True),
    _case(PANEL_BANK + ("panelPlacementOverrides",), dropped=False),
    _case(PANEL_BANK + ("panelConfigOverrides",), dropped=False),
    _case(PANEL_SECTION + ("flowConfig", "snapToColumns"), dropped=True),
    _case(PANEL_SECTION + ("flowConfig", "mobileColumnsPerPage"), dropped=True),
    _case(PANEL_SECTION + ("sorted",), dropped=True),
    _case(PANEL_SECTION + ("sectionSettings",), dropped=True),
    _case(MEDIA_CONFIG + ("actualSize",), dropped=True),
    _case(MEDIA_CONFIG + ("fitToDimension",), dropped=True),
    _case(MEDIA_CONFIG + ("pixelated",), dropped=True),
    _case(MEDIA_CONFIG + ("stepIndex",), dropped=True),
    _case(MEDIA_CONFIG + ("maxGalleryItems",), dropped=True),
    _case(MEDIA_CONFIG + ("maxRuns",), dropped=True),
    _case(MEDIA_CONFIG + ("videoPlaybackSyncEnabled",), dropped=True),
    _case(RUNSET + ("name",), dropped=True),
    _case(RUNSET + ("enabled",), dropped=True),
    _case(RUNSET + ("search",), dropped=False),
    _case(RUNSET + ("grouping",), dropped=True),
    _case(RUNSET + ("sort",), dropped=False),
    _case(RUNSET + ("selections", "bounds"), dropped=True),
    _case(RUNSET + ("expandedRowAddresses",), dropped=True),
    _case(RUN_FEED + ("columnVisible",), dropped=True),
    _case(RUN_FEED + ("columnPinned",), dropped=False),
    _case(RUN_FEED + ("columnWidths",), dropped=True),
    _case(RUN_FEED + ("columnOrder",), dropped=True),
    _case(RUN_FEED + ("pageSize",), dropped=True),
    _case(RUN_FEED + ("onlyShowSelected",), dropped=True),
]


@pytest.fixture(scope="module")
def unedited_save():
    return fetch_then_save(copy.deepcopy(LOADED_SPEC))


@pytest.mark.parametrize("path", PRESERVED_PATHS)
def test_unedited_save_keeps_field(unedited_save, path):
    assert _as_json(_get(unedited_save, path)) == _as_json(_get(LOADED_SPEC, path))


ADDITIVE_TREE = [{"value": "group-a", "children": ["run-a", "run-b"], "skip": False}]


@DROPPED_ON_MAIN
def test_unedited_save_keeps_additive_selection_tree():
    """With root 0 the tree lists the visible runs, grouped. A color-only run
    setting must not flatten it."""
    saved = fetch_then_save(
        _empty_section(
            customRunColors={"run-color": "#00ff00"},
            runSets=[
                {
                    "id": "rs1",
                    "selections": {"root": 0, "bounds": [], "tree": ADDITIVE_TREE},
                }
            ],
        )
    )

    selections = saved["section"]["runSets"][0]["selections"]
    assert selections["root"] == 0
    assert selections["tree"] == ADDITIVE_TREE
    assert saved["section"]["customRunColors"] == {"run-color": "#00ff00"}


@DROPPED_ON_MAIN
def test_enabling_a_run_adds_it_to_an_additive_selection_tree():
    """With root 0, a run the user makes visible must join the tree."""

    def enable_run_b(workspace):
        workspace.runset_settings.run_settings["run-b"] = ws.RunSettings(disabled=False)

    saved = fetch_then_save(
        _empty_section(
            runSets=[
                {
                    "id": "rs1",
                    "selections": {"root": 0, "bounds": [], "tree": ["run-a"]},
                }
            ]
        ),
        edit=enable_run_b,
    )

    selections = saved["section"]["runSets"][0]["selections"]
    assert selections["root"] == 0
    assert sorted(selections["tree"]) == ["run-a", "run-b"]


@DROPPED_ON_MAIN
def test_clearing_a_run_color_removes_it():
    def clear_color(workspace):
        workspace.runset_settings.run_settings["run-a"].color = ""

    saved = fetch_then_save(
        _empty_section(customRunColors={"run-a": "#ff0000"}), edit=clear_color
    )

    assert saved["section"]["customRunColors"] == {}


def test_changing_pinned_columns_replaces_the_pinned_order():
    def repin(workspace):
        workspace.runset_settings.pinned_columns = ["run:displayName", "summary:new"]

    saved = fetch_then_save(
        _empty_section(
            runSets=[
                {
                    "id": "rs1",
                    "runFeed": {
                        "columnVisible": {"run:displayName": True, "summary:old": True},
                        "columnPinned": {"run:displayName": True, "summary:old": True},
                        "columnOrder": ["run:displayName", "summary:old"],
                    },
                }
            ]
        ),
        edit=repin,
    )

    run_feed = saved["section"]["runSets"][0]["runFeed"]
    assert run_feed["columnPinned"] == {"run:displayName": True, "summary:new": True}
    assert run_feed["columnVisible"] == {"run:displayName": True, "summary:new": True}
    assert run_feed["columnOrder"] == ["run:displayName", "summary:new"]
