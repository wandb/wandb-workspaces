import pytest

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws
from wandb_workspaces.utils.colors import is_valid_color, transparent_color


@pytest.mark.parametrize(
    "color",
    [
        "#f00",
        "#ff0000",
        "#ff000080",
        "red",
        "rgb(31, 119, 180)",
        "rgba(0,0,0,0)",
        "hsl(120, 50%, 50%)",
    ],
)
def test_valid_colors(color):
    assert is_valid_color(color)


@pytest.mark.parametrize(
    "color",
    ["", "rgb(31", "rgba(0,0,0,0)19", "#ff000", "rgb(1,2)", None, (31, 119, 180)],
)
def test_invalid_colors(color):
    assert not is_valid_color(color)


@pytest.mark.parametrize(
    "color, expected",
    [
        ("#ff0000", "#ff000019"),
        ("#f00", "#ff000019"),
        ("#ff000080", "#ff000019"),
        ("rgba(0,0,0,0)", "rgba(0,0,0,0.1)"),
        ("rgb(31, 119, 180)", "rgba(31,119,180,0.1)"),
        ("hsl(120, 50%, 50%)", "hsla(120,50%,50%,0.1)"),
        ("red", None),
    ],
)
def test_transparent_color(color, expected):
    assert transparent_color(color) == expected


def test_line_plot_drops_invalid_line_colors():
    lp = wr.LinePlot(
        y=["loss"],
        line_colors={"run:loss": "rgba(0,0,0,0)", "run:acc": "rgb(31", "run:lr": "red"},
    )
    assert lp._to_model().config.override_colors == {
        "run:loss": {"color": "rgba(0,0,0,0)", "transparentColor": "rgba(0,0,0,0.1)"},
        "run:lr": {"color": "red", "transparentColor": "red"},
    }


def test_panel_grid_drops_invalid_run_colors():
    pg = wr.PanelGrid(
        runsets=[
            wr.Runset(
                run_settings={
                    "good": wr.RunSettings(color="#ff0000"),
                    "bad": wr.RunSettings(color="rgb(31"),
                }
            )
        ]
    )
    assert pg._to_model().metadata.custom_run_colors == {"good": "#ff0000"}


def test_workspace_drops_invalid_run_colors():
    workspace = ws.Workspace(
        entity="entity",
        project="project",
        runset_settings=ws.RunsetSettings(
            run_settings={
                "good": ws.RunSettings(color="#ff0000"),
                "bad": ws.RunSettings(color="rgb(31"),
            }
        ),
    )
    assert workspace._to_model().spec.section.custom_run_colors == {"good": "#ff0000"}


def test_workspace_drops_invalid_group_colors():
    workspace = ws.Workspace(
        entity="entity",
        project="project",
        runset_settings=ws.RunsetSettings(
            groupby=[ws.Config("model")],
            group_colors={"vit": "#59A14F", "resnet": "rgb(31"},
        ),
    )
    colors = workspace._to_model().spec.section.custom_run_colors
    assert list(colors.values()) == ["#59A14F"]
