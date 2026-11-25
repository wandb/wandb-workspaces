"""What a save sends for content created through the SDK.

The round-trip tests check what a save does to loaded content. These check
the other half: a workspace, section or panel the user creates in the SDK
must be written the way the app writes hand-made content. Four shapes main
wrote before the save path changed, none of which the write contract rejects:

- a run set with an empty id, unless group colors are set;
- a new section with no `__id__`;
- no Hidden Panels section, or one that is no longer last after adding a
  section to a loaded workspace;
- a default layout block on every panel, all at the same position.
"""

import copy

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws
from wandb_workspaces.expr import Config

from .fake_view_server import FakeViewServer, fetch_then_save, save_workspace
from .spec_harness import SPECS_DIR, load_spec, write_errors

HIDDEN_PANELS = "Hidden Panels"

APP_SPEC = load_spec(SPECS_DIR / "app-panel-sandbox.json")


def _line_plot(**kwargs):
    return wr.LinePlot(x="Step", y=["loss"], **kwargs)


def _new_workspace(**kwargs):
    kwargs.setdefault(
        "sections", [ws.Section(name="Probe", panels=[_line_plot(), _line_plot()])]
    )
    return ws.Workspace(entity="ent", project="proj", name="probe", **kwargs)


def _saved(workspace):
    server = FakeViewServer()
    save_workspace(server, workspace)
    [spec] = server.saved_specs()
    return spec


def _sections(spec):
    return spec["section"]["panelBankConfig"]["sections"]


def _section(spec, name):
    [section] = [s for s in _sections(spec) if s.get("name") == name]
    return section


def _add_section(workspace):
    workspace.sections.append(ws.Section(name="Added", panels=[_line_plot()]))


# Run set id


def test_new_workspace_gives_its_run_set_an_id():
    [runset] = _saved(_new_workspace())["section"]["runSets"]
    assert runset.get("id")


def test_new_workspace_with_group_colors_gives_its_run_set_an_id():
    workspace = _new_workspace(
        runset_settings=ws.RunsetSettings(
            groupby=[Config("lr")], group_colors={"config.lr": "#ff0000"}
        )
    )
    [runset] = _saved(workspace)["section"]["runSets"]
    assert runset.get("id")


def test_loaded_workspace_keeps_its_run_set_id():
    saved = fetch_then_save(copy.deepcopy(APP_SPEC))
    assert saved["section"]["runSets"][0]["id"] == "ijc42mvj2"


# Section __id__


def test_new_workspace_gives_its_sections_an_id():
    assert _section(_saved(_new_workspace()), "Probe").get("__id__")


def test_section_added_to_a_loaded_workspace_gets_an_id():
    saved = fetch_then_save(copy.deepcopy(APP_SPEC), edit=_add_section)
    assert _section(saved, "Added").get("__id__")


def test_loaded_sections_keep_their_ids():
    saved = fetch_then_save(copy.deepcopy(APP_SPEC), edit=_add_section)
    loaded = {s["name"]: s["__id__"] for s in _sections(APP_SPEC)}
    kept = {s["name"]: s.get("__id__") for s in _sections(saved) if s["name"] in loaded}
    assert kept == loaded


def test_a_section_keeps_its_id_across_saves():
    workspace = _new_workspace()
    server = FakeViewServer()
    save_workspace(server, workspace)
    workspace.sections[0].is_open = True
    save_workspace(server, workspace)
    first, second = server.saved_specs()
    assert _section(first, "Probe")["__id__"] == _section(second, "Probe")["__id__"]


# Hidden Panels last


def test_new_workspace_ends_with_hidden_panels():
    assert _sections(_saved(_new_workspace()))[-1]["name"] == HIDDEN_PANELS


def test_hidden_panels_survives_later_saves():
    """The saved spec holds the generated section but `sections` does not;
    the rebuild must keep producing it or the next save deletes it."""
    workspace = _new_workspace()
    server = FakeViewServer()
    save_workspace(server, workspace)
    workspace.sections[0].is_open = True
    save_workspace(server, workspace)
    save_workspace(server, workspace)
    for spec in server.saved_specs():
        assert [s["name"] for s in _sections(spec)] == ["Probe", HIDDEN_PANELS]


def test_section_added_to_a_loaded_workspace_goes_before_hidden_panels():
    saved = fetch_then_save(copy.deepcopy(APP_SPEC), edit=_add_section)
    names = [s["name"] for s in _sections(saved)]
    assert names[-1] == HIDDEN_PANELS
    assert "Added" in names


# Panel layout


def test_panel_with_no_layout_is_saved_without_one():
    panels = _section(_saved(_new_workspace()), "Probe")["panels"]
    assert [p.get("layout") for p in panels] == [None, None]


def test_panel_layout_the_user_set_is_kept():
    layout = wr.Layout(x=8, y=0, w=16, h=8)
    workspace = _new_workspace(
        sections=[ws.Section(name="Probe", panels=[_line_plot(layout=layout)])]
    )
    [panel] = _section(_saved(workspace), "Probe")["panels"]
    assert panel["layout"] == {"x": 8, "y": 0, "w": 16, "h": 8}


# The shape of a new workspace


def test_new_workspace_has_no_stray_root_keys():
    """The app does not write `vizExpanded` or `libraryExpanded` for a new
    workspace, and the write contract rejects them."""
    assert set(_saved(_new_workspace())) == {"section"}


def test_new_workspace_passes_the_write_contract():
    errors = write_errors(_saved(_new_workspace()))
    assert not errors, "\n".join(f"{path}: {message}" for path, message in errors)


def test_new_workspace_writes_its_settings_where_the_app_keeps_them():
    """Workspace settings go in `workspaceSettings.linePlot`, section settings
    in `sectionSettings.linePlot`, not the legacy `settings` and
    `localPanelSettings` blocks the app only migrates from."""
    workspace = _new_workspace(settings=ws.WorkspaceSettings(ignore_outliers=True))
    spec = _saved(workspace)
    section = spec["section"]

    assert "settings" not in section
    line_plot = section["workspaceSettings"]["linePlot"]
    assert line_plot["xAxis"] == "_step"
    assert line_plot["excludeOutliers"] == "exclude-outliers"
    assert "ignoreOutliers" not in line_plot
    assert section["workspaceSettings"]["shouldAutoGeneratePanels"] is False

    probe = _section(spec, "Probe")
    assert "localPanelSettings" not in probe
    assert probe["sectionSettings"]["linePlot"]["smoothingType"] == "none"


def test_app_managed_sections_carry_no_layout_or_settings():
    """The app writes the Hidden Panels section and `panelBankSectionConfig`
    with just their identity and panels."""
    spec = _saved(_new_workspace())
    hidden = _section(spec, HIDDEN_PANELS)
    for section in (hidden, spec["section"]["panelBankSectionConfig"]):
        assert not {"flowConfig", "localPanelSettings", "sectionSettings"} & set(
            section
        )
    assert hidden["isPanelsAuto"] is False
