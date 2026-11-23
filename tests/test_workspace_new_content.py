"""What a save sends for content created through the SDK.

The round-trip tests check what a save does to loaded content. These check
the other half: a workspace, section or panel the user creates in the SDK
must be written the way the app writes hand-made content. Four shapes main
writes today, none of which the write contract rejects:

- a run set with an empty id, unless group colors are set;
- a new section with no `__id__`;
- no Hidden Panels section, or one that is no longer last after adding a
  section to a loaded workspace;
- a default layout block on every panel, all at the same position.

Each is marked `xfail(strict=True)`, so a fix must remove its mark. Only an
AssertionError counts as the expected failure, so a crash still shows.
"""

import copy

import pytest

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws
from wandb_workspaces.expr import Config

from .fake_view_server import FakeViewServer, fetch_then_save, save_workspace
from .spec_harness import SPECS_DIR, load_spec

WRITTEN_ON_MAIN = pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="main writes this shape for new content",
)

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


@WRITTEN_ON_MAIN
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


@WRITTEN_ON_MAIN
def test_new_workspace_gives_its_sections_an_id():
    assert _section(_saved(_new_workspace()), "Probe").get("__id__")


@WRITTEN_ON_MAIN
def test_section_added_to_a_loaded_workspace_gets_an_id():
    saved = fetch_then_save(copy.deepcopy(APP_SPEC), edit=_add_section)
    assert _section(saved, "Added").get("__id__")


def test_loaded_sections_keep_their_ids():
    saved = fetch_then_save(copy.deepcopy(APP_SPEC), edit=_add_section)
    loaded = {s["name"]: s["__id__"] for s in _sections(APP_SPEC)}
    kept = {s["name"]: s.get("__id__") for s in _sections(saved) if s["name"] in loaded}
    assert kept == loaded


# Hidden Panels last


@WRITTEN_ON_MAIN
def test_new_workspace_ends_with_hidden_panels():
    assert _sections(_saved(_new_workspace()))[-1]["name"] == HIDDEN_PANELS


@WRITTEN_ON_MAIN
def test_section_added_to_a_loaded_workspace_goes_before_hidden_panels():
    saved = fetch_then_save(copy.deepcopy(APP_SPEC), edit=_add_section)
    names = [s["name"] for s in _sections(saved)]
    assert names[-1] == HIDDEN_PANELS
    assert "Added" in names


# Panel layout


@WRITTEN_ON_MAIN
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
