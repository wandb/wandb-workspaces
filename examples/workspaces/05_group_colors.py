import os

import wandb_workspaces.reports.v2 as wr  # Panels are Reports API objects
import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# Color grouped runs by their groupby hierarchy. A bare string targets the
# first groupby level; ws.GroupPath(...) targets a nested level. Descendants
# inherit a parent's color unless they set their own.
workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Group colors example",
    sections=[
        ws.Section(
            name="Metrics",
            panels=[
                wr.LinePlot(x="Step", y=["loss"]),
                wr.LinePlot(x="Step", y=["accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        groupby=[ws.Metric("group"), ws.Config("model")],
        group_colors={
            # Parent colors: descendants inherit unless overridden.
            "sweep_alpha": "#4E79A7",
            "sweep_beta": "#E15759",
            # Nested override under sweep_alpha.
            ws.GroupPath("sweep_alpha", "convnext"): "#59A14F",
            # Nested-only colors under sweep_gamma.
            ws.GroupPath("sweep_gamma", "resnet"): "#2A9D8F",
            ws.GroupPath("sweep_gamma", "mlp"): "#F28E2B",
        },
    ),
).save()

print(workspace.url)
