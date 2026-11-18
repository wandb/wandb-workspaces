"""Fetch-then-save regression tests for workspace specs, ported from #156.

Each test loads a stored spec through `Workspace.from_url`, optionally edits
it through the public API, saves it, and checks the spec the save sent. They
only touch JSON in and JSON out, so they hold across a change of the internal
models.

Fixtures declare only keys the view spec schema's read contract declares
(packages/wandb-schemas in wandb/core). Assertions from #156 on keys the
schema calls stray (the root `vizExpanded`, `libraryExpanded` and
`slowWarningHiddenAt`, and `shouldAutoGeneratePanels` under the legacy
`settings`) were not ported: the write contract rejects them, so keeping
them is not frontend behavior.

`xfail(strict=True)` marks a field main drops or rewrites today. When a fix
makes one pass, strict xfail fails the run until its mark is removed.
"""

import copy

import pytest

import wandb_workspaces.workspaces as ws

from .fake_view_server import fetch_then_save

DROPPED_ON_MAIN = pytest.mark.xfail(
    strict=True, reason="main drops or rewrites this field on save"
)


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
    node = spec
    for part in path:
        node = node[part]
    return node


# A workspace as the app stores it, carrying fields the SDK has no attribute for.
LOADED_SPEC = {
    "section": {
        "name": "Original Wrapper",
        "version": 9,
        "panelBankConfig": {
            "state": 1,
            "settings": {
                "autoOrganizePrefix": 1,
                "showEmptySections": True,
                "sortAlphabetically": True,
                "searchQuery": "loss",
            },
            "panelPlacementOverrides": {
                "loss": {"sectionId": "section-1", "orderKey": "a0"}
            },
            "panelConfigOverrides": {
                "loss": {"config": {"chartTitle": "Loss"}, "layout": {"w": 8}}
            },
            "sections": [
                {
                    "__id__": "section-1",
                    "defaultName": "Charts",
                    "name": "Charts",
                    "isOpen": True,
                    "flowConfig": {
                        "snapToColumns": False,
                        "columnsPerPage": 4,
                        "rowsPerPage": 5,
                        "gutterWidth": 24,
                        "boxWidth": 500,
                        "boxHeight": 320,
                        "mobileColumnsPerPage": 1,
                    },
                    "sorted": 1,
                    "localPanelSettings": {
                        "smoothingWeight": 9,
                        "smoothingType": "gaussian",
                        "xAxis": "_runtime",
                        "ignoreOutliers": True,
                    },
                    "sectionSettings": {"linePlot": {"showLegend": False}},
                    "panels": [
                        {
                            "__id__": "media-1",
                            "viewType": "Media Browser",
                            "config": {
                                "chartTitle": "Image Samples",
                                "columnCount": 5,
                                "mediaKeys": ["examples/image"],
                                "mode": "grid",
                                "gridSettings": {"xAxis": "step", "yAxis": "run"},
                                "actualSize": True,
                                "fitToDimension": True,
                                "pixelated": True,
                                "stepIndex": 5,
                                "maxGalleryItems": 100,
                                "maxRuns": 20,
                                "videoPlaybackSyncEnabled": True,
                            },
                            "layout": {"x": 0, "y": 0, "w": 12, "h": 8},
                        }
                    ],
                    "pinned": True,
                }
            ],
        },
        "panelBankSectionConfig": {"pinned": False},
        "customRunColors": {"run-a": "#ff0000"},
        "customRunNames": {"run-a": "Best Run"},
        "workspaceSettings": {
            "linePlot": {"showLegend": False},
            "media": {"maxRuns": 5},
        },
        "semanticLegendSettings": {
            "runColorOptions": "semantic-legend",
            "excludedRunColor": "#cccccc",
        },
        "runSets": [
            {
                "id": "rs1",
                "name": "Custom Run Set",
                "enabled": False,
                "runFeed": {
                    "version": 2,
                    "columnVisible": {"run:name": True, "config:lr": True},
                    "columnPinned": {"run:displayName": True, "config:lr": True},
                    "columnWidths": {"run:name": 222},
                    "columnOrder": ["run:displayName", "config:lr", "summary:loss"],
                    "pageSize": 50,
                    "onlyShowSelected": True,
                },
                "search": {"query": "abc", "isRegex": True},
                "filters": {"op": "OR", "filters": [{"op": "AND", "filters": []}]},
                "grouping": [{"section": "config", "name": "epochs"}],
                "sort": {
                    "keys": [
                        {
                            "key": {"section": "run", "name": "createdAt"},
                            "ascending": False,
                        },
                        {
                            "key": {"section": "config", "name": "pbt.workspace.value"},
                            "ascending": True,
                        },
                        {
                            "key": {"section": "config", "name": "pbt.value.workspace"},
                            "ascending": False,
                        },
                    ]
                },
                "selections": {
                    "root": 1,
                    "bounds": [{"key": {"section": "run", "name": "createdAt"}}],
                    "tree": ["run-b"],
                },
                "expandedRowAddresses": ["0/run-b"],
            }
        ],
        "settings": {
            "xAxis": "_runtime",
            "xAxisMin": 1,
            "xAxisMax": 9,
            "smoothingType": "gaussian",
            "smoothingWeight": 4,
            "ignoreOutliers": True,
        },
        "openRunSet": 3,
        "openViz": False,
    }
}


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
    assert _get(unedited_save, path) == _get(LOADED_SPEC, path)


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
