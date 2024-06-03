import os

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# 1a. You can create filters using basic metrics and python expressions
val_loss_filter = ws.Metric("val_loss") < 1

# 1b. You can also reference filters as they appear in the UI, like `Name`, `Tags`, or `ID`
run_name_filter = ws.Metric("Name") == "smooth-star-4"
run_id_filter = ws.Metric("ID").isin(["1mbku38n", "2u1g3j1c"])

# 2. Create a workspace with filters
workspace = ws.Workspace(
    name="An example workspace using filters",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Validation",
            panels=[
                wr.LinePlot(x="Step", y=["val_loss"]),
                wr.LinePlot(x="Step", y=["val_accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # Passing in a list of filter expressions "AND"s them together.
        filters=[
            ws.Metric("Name") == "smooth-star-4",
            ws.Metric("ID").isin(["1mbku38n", "2u1g3j1c"]),
        ]
    ),
)

workspace.save()
