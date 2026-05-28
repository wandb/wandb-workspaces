"""
Example: Managing Columns in a Report's Runs Table

Demonstrates how to control which columns appear in the runs table inside
a Report's PanelGrid. The Runset API exposes three list fields for
visibility — `pinned_columns`, `visible_columns`, `hidden_columns` — plus
the `lock_columns` toggle.

Locked-columns mode:
    By default, runs tables show every column the underlying runs logged;
    `hidden_columns` drops specific cols, `visible_columns` is a no-op.
    Set `lock_columns=True` to show ONLY cols listed in `pinned_columns`
    or `visible_columns`. The FE exposes the same toggle as the lock icon
    in the runs-table toolbar (Reports edit mode).

Column format: "section:name"
    run     - Built-in run properties (e.g. "run:displayName", "run:state")
    config  - Config parameters (e.g. "config:learning_rate.value")
    summary - Summary metrics (e.g. "summary:accuracy")
    tags    - Run tags (only "tags:__ALL__" is valid)

Nested config uses dot notation:
    {"model": {"lr": 0.001}} → "config:model.lr"
"""

import os

import wandb_workspaces.reports.v2 as wr

entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")


# ============================================================================
# Example 1: Pin a column without hiding others (default permissive mode)
# ============================================================================
# Pinning sticks the column to the left. All other columns the runs logged
# remain visible — lock_columns is left at its default (None / permissive).

report = wr.Report(
    entity=entity,
    project=project,
    title="Pin one column",
    blocks=[
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    pinned_columns=["summary:loss"],
                ),
            ],
            panels=[wr.LinePlot(x="Step", y=["val_loss"])],
        ),
    ],
).save()
print(f"Saved: {report.url}")


# ============================================================================
# Example 2: Locked columns — show ONLY a curated set of columns
# ============================================================================
# Set lock_columns=True to switch to allowlist mode. Only columns listed
# in pinned_columns or visible_columns will appear; all auto-discovered
# config:* and summary:* keys are hidden.

report = wr.Report(
    entity=entity,
    project=project,
    title="Curated column set",
    blocks=[
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    pinned_columns=["summary:accuracy"],
                    visible_columns=[
                        "summary:loss",
                        "config:learning_rate.value",
                        "run:state",
                    ],
                    lock_columns=True,
                ),
            ],
            panels=[wr.LinePlot(x="Step", y=["val_loss", "val_accuracy"])],
        ),
    ],
).save()
print(f"Saved: {report.url}")


# ============================================================================
# Example 3: Hide specific columns without locked mode
# ============================================================================
# Use hidden_columns to drop a few noisy cols while keeping everything else
# visible (default permissive mode).

report = wr.Report(
    entity=entity,
    project=project,
    title="Hide noisy columns",
    blocks=[
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    hidden_columns=[
                        "config:internal_debug_flag.value",
                        "summary:scratch_value",
                    ],
                ),
            ],
            panels=[wr.LinePlot(x="Step", y=["val_loss"])],
        ),
    ],
).save()
print(f"Saved: {report.url}")


# ============================================================================
# Example 4: Custom column order and widths
# ============================================================================

report = wr.Report(
    entity=entity,
    project=project,
    title="Ordered and sized columns",
    blocks=[
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=entity,
                    project=project,
                    pinned_columns=["summary:accuracy", "summary:loss"],
                    column_order=[
                        "summary:accuracy",
                        "summary:loss",
                        "config:learning_rate.value",
                    ],
                    column_widths={
                        "summary:accuracy": 200,
                        "summary:loss": 200,
                        "config:learning_rate.value": 150,
                    },
                ),
            ],
            panels=[wr.LinePlot(x="Step", y=["val_loss"])],
        ),
    ],
).save()
print(f"Saved: {report.url}")


# ============================================================================
# Example 5: Round-trip — load, modify, save
# ============================================================================
# Column config (including lock_columns) survives load/save.

loaded = wr.Report.from_url(report.url)
runset = loaded.blocks[0].runsets[0]
print(f"Loaded pinned:         {runset.pinned_columns}")
print(f"Loaded visible:        {runset.visible_columns}")
print(f"Loaded hidden:         {runset.hidden_columns}")
print(f"Loaded lock_columns: {runset.lock_columns}")

runset.pinned_columns.append("run:state")
loaded.save()
print(f"Re-saved with extra column: {loaded.url}")
