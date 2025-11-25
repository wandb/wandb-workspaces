import os

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# 1. Create a workspace.
workspace = ws.Workspace(name="An example workspace", entity=entity, project=project)


# 2. Add sections with panels (these are the the collapsible blocks in the workspace))
workspace.sections = [
    # For example, put your validation metrics front and center
    # You can pin important sections to keep them at the top of the workspace
    ws.Section(
        name="Validation",
        panels=[
            wr.LinePlot(x="Step", y=["val_loss"]),
            wr.LinePlot(x="Step", y=["val_accuracy"]),
            wr.ScalarChart(metric="f1_score", groupby_aggfunc="mean"),
            wr.ScalarChart(metric="recall", groupby_aggfunc="mean"),
        ],
        is_open=True,
        pinned=True,  # Pinned sections appear at the top of the workspace
    ),
    # And have collapsed sections for just when you need them
    ws.Section(
        name="Training",
        panels=[
            wr.LinePlot(x="Step", y=["train_loss"]),
            wr.LinePlot(x="Step", y=["train_accuracy"]),
        ],
    ),
    # You can also use regex to select multiple metrics dynamically
    ws.Section(
        name="System Metrics",
        panels=[
            wr.LinePlot(
                title="All System Metrics",
                metric_regex="system/.*",  # Matches all metrics starting with "system/"
            ),
        ],
    ),
]


# 3a. Configure settings on the workspace...
workspace.settings = ws.WorkspaceSettings(
    x_min=0,
    x_max=75,
    smoothing_type="gaussian",
    point_visualization_method="bucketing",
)

# 3b. ...or on individual sections...
section = workspace.sections[0]
section.panel_settings = ws.SectionPanelSettings(
    x_min=25,
    x_max=50,
    smoothing_type="none",
)

# 3b. ...or on individual panels (these options depend on the panel type)
panel = section.panels[0]
panel.title = "Validation Loss Custom Title"
panel.title_x = "Custom x-axis title"


# 4. Save the workspace.  This will print a URL to the workspace to the terminal
workspace.save()
