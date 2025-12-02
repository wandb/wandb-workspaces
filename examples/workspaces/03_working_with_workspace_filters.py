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
        # Note: < maps to <=, > maps to >=, and = maps to == internally to match existing UX behavior
        filters="SummaryMetric('accuracy') > 0.95 and Config('learning_rate') = 0.001 and Metric('State') == 'finished'"
    ),
)

workspace_with_string_filters.save()

# ============================================================================
# METHOD 3: Time-based filtering with "within last"
# ============================================================================
# Filter runs by timestamps (e.g., runs created in the last N days/hours/minutes)

# Using FilterExpr with within_last method
workspace_recent_runs = ws.Workspace(
    name="Recent Runs (Last 7 Days)",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Recent Activity",
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # Filter for runs created in the last 7 days
        filters=[
            ws.Metric("CreatedTimestamp").within_last(7, "days"),
        ]
    ),
)

workspace_recent_runs.save()

# Using string filters with within_last operator syntax
workspace_recent_operator = ws.Workspace(
    name="Very Recent Runs (Last 24 Hours)",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Today's Activity",
            panels=[
                wr.LinePlot(x="Step", y=["loss"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # Filter for runs created in the last 24 hours
        # This is the format you'll see when loading from_url()
        filters="Metric('CreatedTimestamp') within_last 24 hours"
    ),
)

workspace_recent_operator.save()

# Combining within_last with other filters using FilterExpr
workspace_recent_successful = ws.Workspace(
    name="Recent Successful Runs - FilterExpr",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Recent Successful Activity",
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # Filter for finished runs created in the last 5 days with high accuracy
        filters=[
            ws.Metric("CreatedTimestamp").within_last(5, "days"),
            ws.Metric("State") == "finished",
            ws.Summary("accuracy") > 0.9,
        ]
    ),
)

workspace_recent_successful.save()

# Same filter using string filters
workspace_recent_successful_operator = ws.Workspace(
    name="Recent Successful Runs - String Filters",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Recent Successful Activity",
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        filters="Metric('CreatedTimestamp') within_last 5 days and State == 'finished' and Summary('accuracy') > 0.9"
    ),
)

workspace_recent_successful_operator.save()

# ============================================================================
# METHOD 4: Filtering by tags
# ============================================================================
# Filter runs by the tags set via wandb.init(tags=[...])
# Use ws.Tags().isin([...]) to match runs with any of the specified tags
# Use ws.Tags().notin([...]) to exclude runs with any of the specified tags

# Using FilterExpr with Tags
workspace_with_tags = ws.Workspace(
    name="Production Runs (Tag Filter)",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Production Experiments",
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # Filter for runs tagged with 'production' or 'release'
        filters=[
            ws.Tags().isin(["production", "release"]),
        ]
    ),
)

workspace_with_tags.save()

# Excluding runs with certain tags
workspace_excluding_tags = ws.Workspace(
    name="Non-Debug Runs (Excluding Tags)",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Real Experiments",
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # Exclude runs tagged with 'debug' or 'test'
        filters=[
            ws.Tags().notin(["debug", "test"]),
        ]
    ),
)

workspace_excluding_tags.save()

# Combining tag filters with other filters
workspace_tags_combined = ws.Workspace(
    name="Best Production Runs",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Top Production Results",
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # Combine tag filter with other conditions
        filters=[
            ws.Tags().isin(["production"]),
            ws.Metric("State") == "finished",
            ws.Summary("accuracy") > 0.9,
        ]
    ),
)

workspace_tags_combined.save()

# Using string filters with tags
workspace_tags_string = ws.Workspace(
    name="Baseline Runs (String Tag Filter)",
    entity=entity,
    project=project,
    sections=[
        ws.Section(
            name="Baseline Experiments",
            panels=[
                wr.LinePlot(x="Step", y=["loss"]),
            ],
            is_open=True,
        ),
    ],
    runset_settings=ws.RunsetSettings(
        # String filter syntax for tags
        filters="Tags() in ['baseline', 'experiment-v1'] and State == 'finished'"
    ),
)

workspace_tags_string.save()
