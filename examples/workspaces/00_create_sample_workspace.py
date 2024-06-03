import os

import wandb_workspaces.reports.v2 as wr  # Panels are Reports API objects
import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# 0. Generate some sample runs with metrics (uncomment below to generate samples)
# generate_sample_runs_with_metrics(entity, project)

# 1. Declare the workspace all at once...
workspace = ws.Workspace(
    name="Example W&B Workspace",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Validation Metrics",
            panels=[
                wr.LinePlot(x="Step", y=["val_loss"]),
                wr.BarPlot(metrics=["val_accuracy"]),
                wr.ScalarChart(metric="f1_score", groupby_aggfunc="mean"),
            ],
            is_open=True,
        ),
    ],
)

# 1b. ...or build it up from parts
# workspace = ws.Workspace(name="Example W&B Workspace", entity=entity, project=project)
# workspace.sections = [...]

# 2. Save it to W&B
workspace.save()
