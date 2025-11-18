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

# 1. Create a report with FilterExpr list
report_with_filterexpr = wr.Report(
    entity=entity,
    project=project,
    title="Report with FilterExpr Filters",
    blocks=[
        wr.H1("Best Performing Runs"),
        wr.P("This report shows only finished runs with high accuracy."),
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    # Passing in a list of FilterExpr "AND"s them together
                    filters=[
                        ws.Summary("accuracy") > 0.95,
                        ws.Config("learning_rate") == 0.001,
                        ws.Metric("State") == "finished",
                    ],
                )
            ],
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
                wr.ScalarChart(metric="accuracy", groupby_aggfunc="max"),
            ],
        ),
        wr.H2("More Filtering Examples"),
        wr.PanelGrid(
            runsets=[
                # Filter by multiple configs
                wr.Runset(
                    entity=entity,
                    project=project,
                    filters=[
                        ws.Config("batch_size") == 32,
                        ws.Config("optimizer") == "adam",
                    ],
                )
            ],
            panels=[wr.BarPlot(metrics=["loss"])],
        ),
    ],
)

report_with_filterexpr.save()

# ============================================================================
# METHOD 2: Using string expressions
# ============================================================================
# Use the following accordingly: Metric('example'), Summary('example'),
# Config('example'), Tags() (no parameter needed)
# Note: Metric('tags') still works for backwards compatibility

report_with_string_filters = wr.Report(
    entity=entity,
    project=project,
    title="Report with String Filters",
    blocks=[
        wr.H1("Low Loss Runs"),
        wr.P("Filtering runs with string expressions."),
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    # String filters use "and" to combine conditions as there is no "or" available
                    # Supported operators: ==, =, !=, <, <=, >, >=
                    # Note: < maps to <=, > maps to >=, and = maps to == internally to match existing UX behavior
                    filters="SummaryMetric('loss') < 0.1 and Metric('State') == 'finished'",
                )
            ],
            panels=[
                wr.LinePlot(x="Step", y=["loss"]),
                wr.ScalarChart(metric="loss", groupby_aggfunc="min"),
            ],
        ),
        wr.H2("Complex Filter Example"),
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    filters="Summary('loss') < 0.5 and Config('model') == 'resnet50' and Metric('State') == 'finished'",
                )
            ],
            panels=[wr.ParallelCoordinatesPlot()],
        ),
    ],
)

report_with_string_filters.save()

# ============================================================================
# METHOD 3: Comparing multiple runsets with different filters
# ============================================================================
report_with_comparison = wr.Report(
    entity=entity,
    project=project,
    title="Comparing Different Model Configurations",
    blocks=[
        wr.H1("Adam vs SGD Optimizer"),
        wr.P("Comparing performance across different optimizers."),
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    name="Adam Optimizer",
                    entity=entity,
                    project=project,
                    filters=[ws.Config("optimizer") == "adam"],
                ),
                wr.Runset(
                    name="SGD Optimizer",
                    entity=entity,
                    project=project,
                    filters=[ws.Config("optimizer") == "sgd"],
                ),
            ],
            panels=[
                wr.LinePlot(x="Step", y=["loss", "accuracy"]),
                wr.ScatterPlot(x="learning_rate", y="accuracy"),
            ],
        ),
    ],
)

report_with_comparison.save()
