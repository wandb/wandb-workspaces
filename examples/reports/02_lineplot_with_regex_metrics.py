import os

import wandb_workspaces.reports.v2 as wr

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# Example 1: Use regex to select all training metrics
report = wr.Report(
    entity=entity,
    project=project,
    title="Training Metrics Report",
    blocks=[
        wr.H1("Training Metrics"),
        wr.P("This report automatically includes all metrics matching 'train/*'"),
        wr.PanelGrid(
            panels=[
                wr.LinePlot(
                    title="All Training Metrics",
                    metric_regex="train/.*",  # Match all metrics starting with "train/"
                ),
            ]
        ),
    ],
)

# Example 2: Use regex to select validation and test metrics
report2 = wr.Report(
    entity=entity,
    project=project,
    title="Validation & Test Metrics",
    blocks=[
        wr.PanelGrid(
            panels=[
                # Select all validation metrics
                wr.LinePlot(
                    title="Validation Metrics",
                    metric_regex="val/.*",
                ),
                # Select all test metrics
                wr.LinePlot(
                    title="Test Metrics",
                    metric_regex="test/.*",
                ),
            ]
        ),
    ],
)

# Example 3: Use regex with different patterns
report3 = wr.Report(
    entity=entity,
    project=project,
    title="System Metrics",
    blocks=[
        wr.PanelGrid(
            panels=[
                # Select all system metrics
                wr.LinePlot(
                    title="System Resources",
                    metric_regex="system/.*",
                ),
                # Select metrics ending with "loss"
                wr.LinePlot(
                    title="All Loss Metrics",
                    metric_regex=".*loss$",  # Match anything ending with "loss"
                ),
            ]
        ),
    ],
)

# Save the report - the regex patterns will be used by the backend
# report.save()  # Uncomment to save
