"""
Example: Managing Columns in the Runs Table

This example demonstrates how to pin important columns to the left side of the runs table.
Pinned columns are also the only visible columns in the table.

Column Format: "section:name"

SECTIONS:
  run              - Built-in run properties (always available) e.g. "run:displayName", "run:state", "run:createdAt", "run:duration"
  config           - Configuration parameters logged at run start e.g. "config:learning_rate.value", "config:batch_size.value"
  summary          - Final metric values from run e.g. "summary:accuracy", "summary:loss"
  tags             - Run tags (only "tags:__ALL__" is valid)
  aggregations_min - Minimum values from history e.g. "aggregations_min:loss", "aggregations_min:acc"
  aggregations_max - Maximum values from history e.g. "aggregations_max:loss", "aggregations_max:acc"

Nested objects use dot notation:
{"model": {"lr": 0.001}} → "config:model.lr"
{"metrics": {"train": {"acc": 0.9}}} → "summary:metrics.train.acc"

Arrays and special W&B types (images, tables) are NOT flattened.

Note: run:displayName is automatically added and pinned first if not explicitly included.
"""

import os

import wandb_workspaces.workspaces as ws

# !! edit to your entity and project !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")

# ============================================================================
# Example 1: Pin only loss metric
# ============================================================================

minimal_workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Show Me the Loss",
    runset_settings=ws.RunsetSettings(
        # Pin just the most important column
        # Note: run:displayName is automatically added and pinned first
        pinned_columns=["summary:loss"],
    ),
)

minimal_workspace.save()
print(f"Minimal workspace saved: {minimal_workspace.url}")

# ============================================================================
# Example 2: Pin multiple columns
# ============================================================================

workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Multiple Columns",
    runset_settings=ws.RunsetSettings(
        # Pin multiple columns
        # run:displayName is automatically added first
        pinned_columns=["summary:loss", "summary:acc", "run:state"],
    ),
)

workspace.save()
print(f"Workspace saved: {workspace.url}")
