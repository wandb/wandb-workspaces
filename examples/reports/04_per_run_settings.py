import os

import wandb_workspaces.reports.v2 as wr

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# Create a report demonstrating per-run color and visibility settings.
# RunSettings lets you control the color and visibility (eye toggle) of
# individual runs in a panel grid, using the run ID as the key.

report = wr.Report(
    entity=entity,
    project=project,
    title="Per-Run Settings Example",
    blocks=[
        wr.H1("Per-Run Color and Visibility"),
        wr.P(
            "Use run_settings on a Runset to set colors and toggle visibility "
            "for individual runs. This is useful for highlighting or hiding "
            "specific runs when comparing experiments."
        ),
        # 1. Set custom colors on specific runs
        wr.H2("Custom Run Colors"),
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    run_settings={
                        "run-id-1": wr.RunSettings(color="#FF0000"),
                        "run-id-2": wr.RunSettings(color="#00FF00"),
                        "run-id-3": wr.RunSettings(color="blue"),
                    },
                ),
            ],
            panels=[wr.LinePlot(x="Step", y=["val_loss"])],
        ),
        # 2. Hide specific runs (eye closed in UI)
        wr.H2("Hidden Runs"),
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    run_settings={
                        "run-id-1": wr.RunSettings(disabled=True),
                    },
                ),
            ],
            panels=[wr.LinePlot(x="Step", y=["val_loss"])],
        ),
        # 3. Combine color and visibility
        wr.H2("Combined Color and Visibility"),
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    run_settings={
                        "run-id-1": wr.RunSettings(color="#FF0000", disabled=True),
                        "run-id-2": wr.RunSettings(color="#00FF00"),
                    },
                ),
            ],
            panels=[wr.LinePlot(x="Step", y=["val_loss"])],
        ),
    ],
)

# Save the report to W&B
report.save()
