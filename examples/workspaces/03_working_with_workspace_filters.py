import os

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# Different field types:
# - Metrics: run-level metadata fields (Name, State, CreatedTimestamp, etc.)
# - Summary Metrics: summary metrics (from wandb.log())
# - Config: hyperparameters from wandb.config
# - Tags: Passed in via the tags param during init

# ============================================================================
# METHOD 1: Using FilterExpr objects
# ============================================================================
# Use the following accordingly: ws.Metric('example'), ws.Summary('example'),
# ws.Config('example'), ws.Tags() (no parameter needed)

workspace = ws.Workspace(
    name="Example workspace using FilterExpr filters",
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
            ws.Summary("accuracy") > 0.95,
            ws.Config("learning_rate") == 0.001,
            ws.Metric("State") == "finished",
        ]
    ),
)

workspace.save()

# ============================================================================
# METHOD 2: Using string expressions
# ============================================================================
# Use the following accordingly: Metric('example'), Summary('example'),
# Config('example'), Tags() (no parameter needed)
# Note: Metric('tags') still works for backwards compatibility

workspace_with_string_filters = ws.Workspace(
    name="Example workspace using string filters",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Best Runs",
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # String filters use "and" to combine conditions as there is no "or" available
        # Supported operators: ==, =, !=, <, <=, >, >=
        # Note: < maps to <=, > maps to >=, and = maps to == internally due to match existing UX behavior
        filters="SummaryMetric('accuracy') > 0.95 and Config('learning_rate') = 0.001 and Metric('State') == 'finished'"
    ),
)

workspace_with_string_filters.save()
