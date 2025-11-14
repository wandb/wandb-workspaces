import os

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# When using FilterExpr objects:
# - Use ws.Summary() for summary values (gets converted correctly)
# - Use ws.Metric() for run-level fields
# - Use ws.Config() for hyperparameters
# - Use ws.Tags() for filtering by tags (no parameter needed)

# When using string expressions:
# - Use SummaryMetric() or Summary() for summary values
# - Use Metric() for run-level fields and logged metrics
# - Use Config() for hyperparameters
# - Use Tags() for filtering by tags (no parameter needed)
#   Note: Metric('tags') still works for backwards compatibility

# ============================================================================
# METHOD 1: Using FilterExpr objects
# ============================================================================

# You can create filters using basic metrics and python expressions
val_loss_filter = ws.Metric("val_loss") < 1

# You can also reference filters as they appear in the UI, like `Name` or `ID`
run_name_filter = ws.Metric("Name") == "smooth-star-4"
run_id_filter = ws.Metric("ID").isin(["1mbku38n", "2u1g3j1c"])

# Different metric types:
# - ws.Metric(): run-level metadata fields (Name, State, CreatedTimestamp, etc.)
# - ws.Summary(): summary metrics (from wandb.log())
# - ws.Config(): hyperparameters from wandb.config
# - ws.Tags(): for filtering by tags (equivalent to ws.Metric("tags") but cleaner)
summary_filter = ws.Summary("accuracy") > 0.95
config_filter = ws.Config("learning_rate") == 0.001
tags_filter = ws.Tags().isin(["experiment-1", "baseline"])

# Create a workspace with FilterExpr list
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

# You can also use Python-like string expressions for filters
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
        # String filters use "and" to combine multiple conditions
        # Supported operators: ==, =, !=, <, <=, >, >=
        # Note: < maps to <=, > maps to >=, and = maps to == internally
        filters="SummaryMetric('accuracy') > 0.95 and Config('learning_rate') = 0.001 and Metric('State') == 'finished'"
    ),
)

workspace_with_string_filters.save()
