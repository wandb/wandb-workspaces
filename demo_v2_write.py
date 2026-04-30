"""Demo: v2 filter write path — before vs after.

On main, saving a v2 workspace writes a broken Pydantic-coerced tree (connectors lost).
On feat/v2-filters-workspace-write:
  - Unchanged v2 filters are written back as the original v2 dict
  - Modified v2 filters are reconverted to v2 format
  - New/legacy workspaces write canonical OR→AND→leaves tree

Run with:
    WANDB_API_KEY=<key> WANDB_BASE_URL=http://localhost:9001 python demo_v2_write.py
"""

import json

import wandb_workspaces.workspaces as ws
from wandb_workspaces.workspaces import internal
from wandb_workspaces.workspaces.internal import gql

ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr22"
VIEW_NAME = "462wyf8o8ac"
V2_WORKSPACE_URL = f"http://localhost:9001/{ENTITY}/{PROJECT}?nw={VIEW_NAME}"


def banner(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def fetch_backend_filters(view_display_name):
    """Fetch raw filter JSON from the backend by display name."""
    api = __import__("wandb").Api()
    query = gql("""
    query Views($entityName: String, $name: String) {
        project(name: $name, entityName: $entityName) {
            allViews(viewType: "project-view") {
                edges { node { name displayName spec } }
            }
        }
    }
    """)
    response = api.client.execute(query, {"entityName": ENTITY, "name": PROJECT})
    for e in response["project"]["allViews"]["edges"]:
        if e["node"]["displayName"] == view_display_name:
            spec = json.loads(e["node"]["spec"])
            return spec["section"]["runSets"][0]["filters"]
    return None


def print_filters(filters):
    if isinstance(filters, dict):
        print(json.dumps(filters, indent=2))
    else:
        print(json.dumps(filters, indent=2, default=lambda o: o.__dict__ if hasattr(o, '__dict__') else str(o)))


# # ══════════════════════════════════════════════════════════════════════════════
# # Test 1: Load v2 workspace, save unchanged → should preserve raw v2 dict
# # ══════════════════════════════════════════════════════════════════════════════
# banner("Test 1: Save v2 workspace UNCHANGED")

# workspace = ws.Workspace.from_url(V2_WORKSPACE_URL)
# print(f"Loaded:  {workspace.name}")
# print(f"Filters: {workspace.runset_settings.filters}")
# print()

# workspace.name = "Write Test 1 - Unchanged V2"
# workspace.save()

# backend = fetch_backend_filters("Write Test 1 - Unchanged V2")
# print("Backend filters after save:")
# print_filters(backend)


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: Load v2 workspace, modify filters, save → should write v2 format
# ══════════════════════════════════════════════════════════════════════════════
# banner("Test 2: Save v2 workspace with MODIFIED filters")

# workspace = ws.Workspace.from_url(V2_WORKSPACE_URL)
# print(f"Loaded:  {workspace.name}")
# print(f"Original: {workspace.runset_settings.filters}")

# workspace.runset_settings.filters = (
#     'Metric("Name") == "exile" or Metric("Name") == "betty"'
#     ' and (Metric("State") == "finished" or Metric("Name") == "cardigan")'
# )
# print(f"Modified: {workspace.runset_settings.filters}")
# print()

# workspace.name = "Write Test 2 - Modified V2"
# workspace.save()

# backend = fetch_backend_filters("Write Test 2 - Modified V2")
# print("Backend filters after save:")
# print_filters(backend)


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: Create NEW workspace with AND-only filters → should write legacy tree
# ══════════════════════════════════════════════════════════════════════════════
# banner("Test 3: Create NEW workspace (legacy AND-only filters)")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="Write Test - New Legacy View",
#     runset_settings=ws.RunsetSettings(
#         filters='Config("lr") == 0.01 and Metric("State") == "finished"',
#     ),
# )

# workspace.save()

# backend = fetch_backend_filters("Write Test 3 - New Legacy")
# print("Backend filters after save:")
# print_filters(backend)
