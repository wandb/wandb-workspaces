import os

import wandb_workspaces.reports.v2 as wr

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# Create a report with MediaBrowser panels using different grid configurations
report = wr.Report(
    entity=entity,
    project=project,
    title="Media Browser Axis Examples",
    blocks=[
        wr.H1("Media Browser with Custom Axes"),
        wr.P(
            "This report demonstrates different ways to configure the axes "
            "in MediaBrowser panels for organizing media in both gallery and grid modes."
        ),
        wr.H2("Gallery Mode Examples"),
        wr.PanelGrid(
            panels=[
                wr.MediaBrowser(
                    title="Gallery by Step",
                    media_keys=["train_image"],
                    gallery_axis="step",
                ),
                wr.MediaBrowser(
                    title="Gallery by Run",
                    media_keys=["train_image"],
                    gallery_axis="run",
                ),
            ]
        ),
        wr.H2("Grid Mode Examples"),
        wr.PanelGrid(
            panels=[
                wr.MediaBrowser(
                    title="Training Images",
                    media_keys=["train_image"],
                    grid_x_axis="step",
                    grid_y_axis="run",
                )
            ]
        ),
        wr.PanelGrid(
            panels=[
                wr.MediaBrowser(
                    title="Validation Samples",
                    media_keys=["val_image"],
                    grid_x_axis="index",
                    grid_y_axis="run",
                )
            ]
        ),
        wr.H2("Explicit Mode Selection"),
        wr.P(
            "If you configure both gallery and grid axes, you must explicitly specify the mode. "
            "This allows you to prepare both configurations but choose which one to display."
        ),
        wr.PanelGrid(
            panels=[
                wr.MediaBrowser(
                    title="Grid Mode (Explicit)",
                    media_keys=["image"],
                    mode="grid",
                    gallery_axis="step",
                    grid_x_axis="step",
                    grid_y_axis="run",
                )
            ]
        ),
    ],
)

# Save the report to W&B
report.save()
