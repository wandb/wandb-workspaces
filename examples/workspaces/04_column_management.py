"""
Example: Managing Columns in the Runs Table

This example demonstrates how to:
- Discover available columns in your project using fetch_project_fields()
- Pin important columns to the left
- Control which columns are visible (all others are automatically hidden)
- Set the order of columns
- Set custom column widths

Discovering Available Columns:
Use ws.fetch_project_fields() to discover what fields are available in your project
before configuring your workspace. This returns all fields in the SDK format.

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

# ============================================================================
# Example 0: Discovering Available Columns
# ============================================================================
# Before configuring columns, you can discover what fields are available
# in your project using fetch_project_fields()

print("Fetching available fields from project...")
all_fields = ws.fetch_project_fields(entity=entity, project=project)

print(f"\nFound {len(all_fields)} available fields:")
# Filter and display by category
summary_fields = [f for f in all_fields if f.startswith("summary:")]
config_fields = [f for f in all_fields if f.startswith("config:")]
aggregation_fields = [f for f in all_fields if f.startswith("aggregations_")]

print(f"  Summary metrics ({len(summary_fields)}): {summary_fields[:5]}...")
print(f"  Config params ({len(config_fields)}): {config_fields[:5]}...")
print(f"  Aggregations ({len(aggregation_fields)}): {aggregation_fields[:3]}...")
print()

# You can also filter fields by type
print("Fetching only numeric summary metrics...")
numeric_summary = ws.fetch_project_fields(
    entity=entity, project=project, columns=["summary_metrics"], types=["number"]
)
print(f"Found {len(numeric_summary)} numeric summary fields: {numeric_summary[:5]}...")
print()

# ============================================================================
# Example 1: Pin only loss (run:displayName is automatically added and pinned first)
# ============================================================================

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

# ============================================================================
# Example 2: Pin multiple columns and show additional unpinned columns
# ============================================================================

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

# ============================================================================
# Example 3: Using Fetched Fields to Create a Dynamic Workspace
# ============================================================================
# This example shows how to discover fields and use them to configure columns

print("\n" + "=" * 60)
print("Creating a workspace from discovered fields...")
print("=" * 60)

# Step 1: Fetch all fields
available_fields = ws.fetch_project_fields(entity=entity, project=project)

# Step 2: Filter for fields of interest
# Let's find all summary metrics and config params
summary_metrics = [f for f in available_fields if f.startswith("summary:")]
config_params = [f for f in available_fields if f.startswith("config:")]

print(f"\nDiscovered {len(summary_metrics)} summary metrics")
print(f"Discovered {len(config_params)} config parameters")

# Step 3: Select specific fields you want to show
# Let's pin the first 2 summary metrics and show a few more
columns_to_pin = summary_metrics[:2] if len(summary_metrics) >= 2 else summary_metrics
columns_to_show = summary_metrics[:4] if len(summary_metrics) >= 4 else summary_metrics

# Add some config params to visible columns if available
if config_params:
    columns_to_show.extend(config_params[:2])

print(f"\nPinning columns: {columns_to_pin}")
print(f"Showing columns: {columns_to_show}")

# Step 4: Create workspace with the discovered fields
dynamic_workspace = ws.Workspace(
    entity=entity,
    project=project,
    name="Dynamic Columns from Discovery",
    runset_settings=ws.RunsetSettings(
        pinned_columns=columns_to_pin,
        visible_columns=columns_to_show,
        column_order=columns_to_show,
        column_widths={
            # Set widths for pinned columns
            col: 180
            for col in columns_to_pin
        },
    ),
)

dynamic_workspace.save()
print(f"\nDynamic workspace saved: {dynamic_workspace.url}")
print("Note: Columns were automatically discovered and configured!")
