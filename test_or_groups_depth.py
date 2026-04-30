"""Quick smoke test for Or / And / Group filter construction."""

import os
os.environ["WANDB_BASE_URL"] = "http://localhost:9001"

import wandb_workspaces.workspaces as ws

entity = "marie-barrramsey-wb"
project = "taylor-pr23"

# ── 1. Simple OR ────────────────────────────────────────────────────
workspace_or = ws.Workspace(
    name="Test: Simple OR",
    entity=entity,
    project=project,
    runset_settings=ws.RunsetSettings(
        filters=ws.Or(
            ws.Config("lr") == 0.01,
            ws.Config("lr") == 0.1,
        )
    ),
)
workspace_or.save()
print("Saved: Simple OR")

# ── 2. OR with AND branches ─────────────────────────────────────────
workspace_or_and = ws.Workspace(
    name="Test: OR with AND branches",
    entity=entity,
    project=project,
    runset_settings=ws.RunsetSettings(
        filters=ws.Or(
            ws.And(ws.Config("lr") == 0.01, ws.Metric("State") == "finished"),
            ws.Config("lr") == 0.1,
        )
    ),
)
workspace_or_and.save()
print("Saved: OR with AND branches")

# ── 3. AND with a grouped OR (parentheses) ──────────────────────────
workspace_group = ws.Workspace(
    name="Test: AND with grouped OR",
    entity=entity,
    project=project,
    runset_settings=ws.RunsetSettings(
        filters=ws.And(
            ws.Config("lr") == 0.01,
            ws.Group(ws.Or(
                ws.Metric("State") == "finished",
                ws.Config("epochs") == 10,
            )),
        )
    ),
)
workspace_group.save()
print("Saved: AND with grouped OR")

# ── 4. String equivalents ───────────────────────────────────────────
workspace_str_or = ws.Workspace(
    name="Test: String OR",
    entity=entity,
    project=project,
    runset_settings=ws.RunsetSettings(
        filters="Config('lr') == 0.01 or Config('lr') == 0.1"
    ),
)
workspace_str_or.save()
print("Saved: String OR")

workspace_str_group = ws.Workspace(
    name="Test: String AND with grouped OR",
    entity=entity,
    project=project,
    runset_settings=ws.RunsetSettings(
        filters="Config('lr') == 0.01 and (Metric('State') == 'finished' or Config('epochs') == 10)"
    ),
)
workspace_str_group.save()
print("Saved: String AND with grouped OR")

print("\nAll workspaces saved!")
