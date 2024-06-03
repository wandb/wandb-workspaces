import os

import wandb_workspaces.reports.v2 as wr

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# 0. Generate some sample runs with metrics.  (uncomment below to generate samples)
# generate_sample_runs_with_metrics(entity, project)

# 1. Declare the report
report = wr.Report(
    entity=entity,
    project=project,
    title="Example W&B Report",
    blocks=[
        wr.H1("This is a heading"),
        wr.P("Some amazing insightful text about your project"),
        wr.H2(
            "This heading is collapsed",
            collapsed_blocks=[wr.P("Our model is great!")],
        ),
        wr.PanelGrid(
            panels=[
                wr.LinePlot(x="Step", y=["val_loss"]),
                wr.BarPlot(metrics=["val_accuracy"]),
                wr.ScalarChart(metric="f1_score", groupby_aggfunc="mean"),
            ]
        ),
    ],
)

# 2. Save the report to W&B
report.save()
