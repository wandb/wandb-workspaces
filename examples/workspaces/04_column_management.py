"""
Example: Managing Columns in the Runs Table

This example demonstrates how to:
- Pin important columns to the left
- Control which columns are visible (all others are automatically hidden)
- Set the order of columns
- Set custom column widths

Column names use the format: "section:name"
- Run columns: "run:displayName", "run:state", "run:createdAt", "run:duration"
- Summary metrics: "summary:metric_name" (e.g., "summary:accuracy", "summary:loss")
- Config params: "config:param_name.value" (e.g., "config:learning_rate.value", "config:batch_size.value")
- Aggregation min: "aggregations_min:metric_name" (e.g., "aggregations_min:loss", "aggregations_min:acc")
- Aggregation max: "aggregations_max:metric_name" (e.g., "aggregations_max:loss", "aggregations_max:acc")
- Tags: "tags:__ALL__" (this is the only valid value for tags as all tags are displayed in a single column)

Note: When you specify pinned_columns or visible_columns, all columns not explicitly
listed are automatically hidden. Just specify what you want to see.
"""

import os

import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# Example 1: Pin only loss (run:displayName is automatically added and pinned first)
minimal_workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Show Me the Loss",
    runset_settings=ws.RunsetSettings(
        # Pin just the most important columns
        # Note: run:displayName is automatically added to pinned_columns if not present
        pinned_columns=["summary:loss"],
        # They must be in visible
        visible_columns=["summary:loss"],
        # and in order (run:displayName is automatically placed first)
        column_order=["summary:loss"],
        column_widths={
            "summary:loss": 200,
        },
    ),
)

minimal_workspace.save()
print(f"Minimal workspace saved: {minimal_workspace.url}")

# Example 2: Pin multiple columns and show additional unpinned columns
workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Multiple Columns",
    runset_settings=ws.RunsetSettings(
        pinned_columns=["summary:loss"],  # run:displayName auto-added
        # Visible columns includes pinned columns plus additional unpinned ones
        visible_columns=["summary:loss", "summary:acc", "run:state"],
        column_order=["summary:loss", "summary:acc", "run:state"],
        column_widths={
            "summary:loss": 200,
        },
    ),
)

workspace.save()
print(f"Workspace saved: {workspace.url}")
