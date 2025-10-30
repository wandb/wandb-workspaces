"""
Example: Managing Columns in the Runs Table

This example demonstrates how to:
- Pin important columns to the left
- Control which columns are visible
- Set the order of columns
- Set custom column widths

Column names use the format: "section:name"
- Run columns: "run:displayName", "run:state", "run:createdAt", "run:duration"
- Summary metrics: "summary:metric_name" (e.g., "summary:accuracy", "summary:val_loss")
- Config params: "config:param_name" (e.g., "config:learning_rate", "config:batch_size")
- Tags: "tags:__ALL__"
"""

import os

import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# Example 1: Pin only loss (and run name which is always required)
minimal_workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Show Me the Loss",
    runset_settings=ws.RunsetSettings(
        # Pin just the most important columns
        pinned_columns={
            "run:displayName": True,
            "summary:loss": True,
        },
        # They must be in visible
        visible_columns={
            "run:displayName": True,
            "summary:loss": True,
        },
        # and in order
        column_order=["run:displayName", "summary:loss"],
        column_widths={
            "summary:loss": 200,
        },
    ),
)

minimal_workspace.save()
print(f"Minimal workspace saved: {minimal_workspace.url}")

# Example 2: Pin only loss and ONLY show loss (and run name which is always required)
# NB: You must set ALL other columns to False to achieve this behavior
workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Only loss",
    runset_settings=ws.RunsetSettings(
        pinned_columns={
            "run:displayName": True,
            "summary:loss": True,
        },
        visible_columns={
            "config:architecture.value": False,
            "config:dataset.value": False,
            "config:epochs.value": False,
            "config:learning_rate.value": False,
            "run:createdAt": False,
            "run:displayName": True,
            "run:duration": False,
            "run:name": False,
            "run:notes": False,
            "run:state": False,
            "run:sweep": False,
            "run:username": False,
            "summary:acc": False,
            "summary:loss": True,
            "tags:__ALL__": False,
        },
        column_order=[
            "run:displayName",
            "summary:loss",
        ],
        column_widths={
            "summary:loss": 200,
        },
    ),
)

workspace.save()
print(f"Workspace saved: {workspace.url}")
