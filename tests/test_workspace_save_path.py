"""How a save is built: the loaded spec with the user's edits applied, checked
against the view spec schema's contracts."""

import copy

import wandb_workspaces.workspaces as ws

from .fake_view_server import (
    FakeViewServer,
    capture_termwarns,
    fetch_then_save,
    load_workspace,
    save_workspace,
)
from .spec_harness import SPECS_DIR, load_spec, minimal_spec, run_set

APP_SPEC = load_spec(SPECS_DIR / "app-panel-sandbox.json")

MODERN_LINE_PLOT = {
    "xAxis": "_step",
    "smoothingType": "gaussian",
    "smoothingWeight": 3,
    "excludeOutliers": "exclude-outliers",
    "showLegend": False,
    "showOriginalAfterSmoothing": True,
}


def test_workspace_settings_are_read_from_the_modern_block_and_edited_in_place():
    """The app keeps workspace settings in `workspaceSettings.linePlot`. The
    SDK reads them from there, and an edit changes only the key edited."""
    spec = minimal_spec(
        workspaceSettings={
            "linePlot": dict(MODERN_LINE_PLOT),
            "scatterDefaultByWorkspaceType": True,
        }
    )
    server = FakeViewServer(spec=spec)
    workspace = load_workspace(server)

    assert workspace.settings.smoothing_type == "gaussian"
    assert workspace.settings.smoothing_weight == 3
    assert workspace.settings.ignore_outliers is True
    assert workspace.settings.remove_legends_from_panels is True

    workspace.settings.smoothing_weight = 5
    save_workspace(server, workspace)
    [saved] = server.saved_specs()

    assert saved["section"]["workspaceSettings"] == {
        "linePlot": {**MODERN_LINE_PLOT, "smoothingWeight": 5},
        "scatterDefaultByWorkspaceType": True,
    }
    assert "settings" not in saved["section"]


def test_editing_legacy_workspace_settings_writes_the_modern_block():
    """A workspace saved before `workspaceSettings` has only the legacy
    `settings`. An edit writes the modern block, which the app reads first;
    the legacy block is sent as loaded."""
    legacy = {"xAxis": "_step", "smoothingType": "none", "smoothingWeight": 0}
    server = FakeViewServer(spec=minimal_spec(settings=dict(legacy)))
    workspace = load_workspace(server)
    workspace.settings.ignore_outliers = True
    save_workspace(server, workspace)
    [saved] = server.saved_specs()

    # The app's migration of the stored block plus the edit: no SDK default
    # the stored block did not have.
    assert saved["section"]["workspaceSettings"] == {
        "linePlot": {**legacy, "excludeOutliers": "exclude-outliers"}
    }
    assert saved["section"]["settings"] == legacy


def test_legacy_settings_the_sdk_does_not_model_survive_an_edit():
    """The modern block is built from the stored legacy block, so a key the
    SDK has no attribute for moves with the rest, and a current key stored
    in the legacy block is read."""
    legacy = {
        "xAxis": "_step",
        "xAxisFormat": "datetime",
        "displayFullRunName": True,
        "excludeOutliers": "exclude-outliers",
    }
    server = FakeViewServer(spec=minimal_spec(settings=dict(legacy)))
    workspace = load_workspace(server)
    assert workspace.settings.ignore_outliers is True

    workspace.settings.smoothing_weight = 5
    save_workspace(server, workspace)
    [saved] = server.saved_specs()

    assert saved["section"]["workspaceSettings"] == {
        "linePlot": {**legacy, "smoothingWeight": 5}
    }


def test_a_modern_block_holding_only_ref_is_filled_from_the_legacy_block():
    """The app reads `workspaceSettings` as soon as it has a key other than
    `ref`, so a partial block would make it drop every legacy setting."""
    legacy = {"xAxis": "_step", "smoothingType": "gaussian", "smoothingWeight": 3}
    ref = {"type": "runs", "viewID": "v", "id": "r"}
    spec = minimal_spec(settings=dict(legacy), workspaceSettings={"ref": ref})
    server = FakeViewServer(spec=spec)
    workspace = load_workspace(server)
    workspace.settings.smoothing_weight = 9
    save_workspace(server, workspace)
    [saved] = server.saved_specs()

    assert saved["section"]["workspaceSettings"] == {
        "ref": ref,
        "linePlot": {**legacy, "smoothingWeight": 9},
    }


def test_editing_legacy_section_settings_writes_the_modern_block():
    legacy = {"xAxis": "_step", "smoothingWeight": 2, "colorRunNames": False}
    spec = minimal_spec()
    spec["section"]["panelBankConfig"]["sections"] = [
        _bank_section("s1", "A", localPanelSettings=dict(legacy))
    ]
    server = FakeViewServer(spec=spec)
    workspace = load_workspace(server)
    workspace.sections[0].panel_settings.smoothing_weight = 7
    save_workspace(server, workspace)
    [saved] = server.saved_specs()

    [section] = saved["section"]["panelBankConfig"]["sections"]
    assert section["sectionSettings"] == {"linePlot": {**legacy, "smoothingWeight": 7}}
    assert section["localPanelSettings"] == legacy


def test_an_unedited_legacy_workspace_is_sent_as_loaded():
    spec = minimal_spec(settings={"xAxis": "_step", "smoothingWeight": 2})
    spec["section"]["panelBankConfig"]["sections"] = [
        _bank_section("s1", "A", localPanelSettings={"smoothingWeight": 1})
    ]
    assert fetch_then_save(copy.deepcopy(spec)) == spec


def _bank_section(id, name, **overrides):
    section = {
        "__id__": id,
        "name": name,
        "isOpen": False,
        "panels": [],
        "sorted": 0,
        "pinned": False,
        "isPanelsAuto": False,
    }
    section.update(overrides)
    return section


def test_an_edited_panel_in_an_auto_section_is_marked_custom():
    """The app's save keeps only `isAuto: false` panels in an auto section
    and regenerates the rest, so the edit must mark the panel custom. The
    untouched panel is sent as loaded, and so is everything on a second
    save."""
    panels = [
        {
            "__id__": "p1",
            "viewType": "Run History Line Plot",
            "config": {"chartTitle": "loss", "metrics": ["loss"], "xAxis": "_step"},
        },
        {
            "__id__": "p2",
            "viewType": "Run History Line Plot",
            "config": {"chartTitle": "acc", "metrics": ["acc"], "xAxis": "_step"},
        },
    ]
    spec = minimal_spec()
    spec["section"]["panelBankConfig"]["sections"] = [
        _bank_section("s1", "A", panels=panels, isPanelsAuto=True)
    ]
    server = FakeViewServer(spec=spec)
    workspace = load_workspace(server)
    workspace.sections[0].panels[0].title = "training loss"
    save_workspace(server, workspace)
    save_workspace(server, workspace)
    first, second = server.saved_specs()

    edited, untouched = first["section"]["panelBankConfig"]["sections"][0]["panels"]
    assert edited["config"]["chartTitle"] == "training loss"
    assert edited["isAuto"] is False
    assert untouched == panels[1]
    assert second == first


def test_a_color_only_run_setting_leaves_an_additive_tree_alone(monkeypatch):
    """With `root: 0` the tree lists the visible runs. A `RunSettings` made
    only to set a color says nothing about visibility, so it neither joins
    the tree nor, when the tree is grouped, warns."""
    warnings = capture_termwarns(monkeypatch)
    grouped = [{"value": "group-a", "children": ["run-a"], "skip": False}]
    spec = minimal_spec(
        runSets=[run_set(selections={"root": 0, "bounds": [], "tree": grouped})]
    )
    server = FakeViewServer(spec=spec)
    workspace = load_workspace(server)
    workspace.runset_settings.run_settings["run-c"] = ws.RunSettings(color="red")
    save_workspace(server, workspace)
    [saved] = server.saved_specs()

    assert saved["section"]["runSets"][0]["selections"]["tree"] == grouped
    assert saved["section"]["customRunColors"]["run-c"] == "red"
    assert warnings == []


# What the save path relies on: the rebuild is a pure function of the
# public objects, so saving again without an edit sends the same spec.


def test_saving_a_new_workspace_again_sends_the_same_spec():
    workspace = ws.Workspace(
        entity="ent", project="proj", sections=[ws.Section(name="S")]
    )
    server = FakeViewServer()
    assert workspace._rebuilt_spec() == workspace._rebuilt_spec()
    save_workspace(server, workspace)
    assert workspace._rebuilt_spec() == workspace._rebuilt_spec()
    save_workspace(server, workspace)
    first, second = server.saved_specs()
    assert second == first


def test_saving_a_loaded_workspace_again_sends_the_same_spec():
    server = FakeViewServer(spec=copy.deepcopy(APP_SPEC))
    workspace = load_workspace(server)
    save_workspace(server, workspace)
    save_workspace(server, workspace)
    first, second = server.saved_specs()
    assert first == APP_SPEC
    assert second == APP_SPEC


def test_an_edit_lands_on_its_own_section_when_hidden_panels_was_loaded_first():
    """The rebuild puts Hidden Panels last, so the rebuilt sections are a
    permutation of the loaded ones; each edit must follow its section."""
    spec = minimal_spec()
    spec["section"]["panelBankConfig"]["sections"] = [
        _bank_section("hp", "Hidden Panels", unmodeled="hp"),
        _bank_section("a", "A", unmodeled="a"),
    ]
    server = FakeViewServer(spec=spec)
    workspace = load_workspace(server)
    workspace.sections[1].is_open = True
    save_workspace(server, workspace)
    [saved] = server.saved_specs()

    sections = {s["name"]: s for s in saved["section"]["panelBankConfig"]["sections"]}
    assert sections["A"]["isOpen"] is True
    assert sections["A"]["unmodeled"] == "a"
    assert sections["Hidden Panels"]["isOpen"] is False
    assert sections["Hidden Panels"]["unmodeled"] == "hp"


def test_section_settings_are_read_from_the_modern_block_and_edited_in_place():
    section = {
        "__id__": "s1",
        "name": "Charts",
        "isOpen": True,
        "panels": [],
        "sectionSettings": {
            "linePlot": {"smoothingType": "average", "smoothingWeight": 2}
        },
    }
    spec = minimal_spec(
        panelBankConfig={"state": 1, "settings": {}, "sections": [section]}
    )
    server = FakeViewServer(spec=spec)
    workspace = load_workspace(server)

    assert workspace.sections[0].panel_settings.smoothing_type == "average"

    workspace.sections[0].panel_settings.smoothing_weight = 4
    save_workspace(server, workspace)
    [saved] = server.saved_specs()
    [saved_section] = saved["section"]["panelBankConfig"]["sections"]

    assert saved_section["sectionSettings"]["linePlot"]["smoothingWeight"] == 4
    assert saved_section["sectionSettings"]["linePlot"]["smoothingType"] == "average"
    assert "localPanelSettings" not in saved_section


def test_a_second_save_starts_from_the_first():
    """After a save, the next edit is applied onto what was just stored, so
    fields the SDK does not model survive a second save too."""
    server = FakeViewServer(spec=copy.deepcopy(APP_SPEC))
    workspace = load_workspace(server)
    workspace.sections[0].is_open = False
    save_workspace(server, workspace)
    workspace.runset_settings.query = "loss"
    save_workspace(server, workspace)

    first, second = server.saved_specs()
    assert second["section"]["runSets"][0]["search"]["query"] == "loss"
    assert second["section"]["panelBankConfig"]["sections"][0]["isOpen"] is False
    assert second["section"]["customRunNames"] == APP_SPEC["section"]["customRunNames"]
    assert second["section"]["runSets"][0]["runFeed"]["pageSize"] == 20


def test_keys_the_write_contract_rejects_are_sent_as_loaded_with_a_warning(monkeypatch):
    """The app carries `vizExpanded` through from the stored row and the
    write contract rejects it. The SDK does the same: it is sent back as
    loaded, and the warning says so."""
    warnings = capture_termwarns(monkeypatch)
    spec = copy.deepcopy(APP_SPEC)
    spec["vizExpanded"] = False

    saved = fetch_then_save(spec)

    assert saved["vizExpanded"] is False
    [warning] = [w for w in warnings if "write contract" in w]
    assert "sent back as loaded" in warning
    assert ".vizExpanded" in warning


def test_a_spec_outside_the_read_contract_still_loads_with_a_warning(monkeypatch):
    """A stored run set without `selections` fails the read contract. The
    app loads it anyway, and so does the SDK."""
    warnings = capture_termwarns(monkeypatch)
    spec = copy.deepcopy(APP_SPEC)
    del spec["section"]["runSets"][0]["selections"]

    workspace = load_workspace(FakeViewServer(spec=spec))

    assert isinstance(workspace, ws.Workspace)
    [warning] = [w for w in warnings if "read contract" in w]
    assert "selections" in warning
