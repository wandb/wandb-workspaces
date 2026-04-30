"""Show how the outer parens cause nesting, step by step, on a real workspace."""

import json
import os
os.environ["WANDB_BASE_URL"] = "http://localhost:9001"

import wandb_workspaces.workspaces as ws
from wandb_workspaces.workspaces import internal
from wandb_workspaces import expr

URL = "http://localhost:9001/marie-barrramsey-wb/taylor-pr23?nw=2hsd1f6yjec"
VIEW_NAME = "2hsd1f6yjec"


def get_raw_filters(entity, project):
    """Fetch raw filters from the backend."""
    view_dict = internal.get_view_dict(entity, project, VIEW_NAME)
    spec = json.loads(view_dict["spec"]) if isinstance(view_dict["spec"], str) else view_dict["spec"]
    return spec.get("section", {}).get("runSets", [{}])[0].get("filters", {})


# ── Step 1: Read current filters ─────────────────────────────────────
workspace = ws.Workspace.from_url(URL)
raw = get_raw_filters(workspace.entity, workspace.project)

print("=== Step 1: SDK reads filters from backend ===")
print(f"  String shown to user: {workspace.runset_settings.filters}")
print(f"  Raw backend tree:")
print(json.dumps(raw, indent=2))

# ── Step 2: User appends a new filter ────────────────────────────────
print("\n=== Step 2: User appends ' and Config(\"lr\") == 0.01' ===")
current = workspace.runset_settings.filters
if current:
    workspace.runset_settings.filters = current + " and Config('lr') == 0.01"
else:
    print("  (Filters are empty, setting initial filters first)")
    workspace.runset_settings.filters = "Metric('Name') == 'folklore' and Metric('Name') == 'evermore'"
    workspace.save()
    workspace = ws.Workspace.from_url(URL)
    workspace.runset_settings.filters = workspace.runset_settings.filters + " and Config('lr') == 0.01"
print(f"  Modified string: {workspace.runset_settings.filters}")

# ── Step 3: Save and see what the backend gets ───────────────────────
print("\n=== Step 3: Save to backend ===")
workspace.save()
raw_after = get_raw_filters(workspace.entity, workspace.project)
print(f"  Backend tree after save:")
print(json.dumps(raw_after, indent=2))

# ── Step 4: Read back to show next string ────────────────────────────
print("\n=== Step 4: Read back - what would the user see next? ===")
ws2 = ws.Workspace.from_url(URL)
print(f"  String shown to user: {ws2.runset_settings.filters}")
