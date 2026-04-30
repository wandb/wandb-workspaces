import json

import wandb
import wandb_workspaces.workspaces as ws
import wandb_workspaces.reports.v2 as wr
from wandb_workspaces.workspaces.internal import gql

ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr22"

# --- Load the v2 workspace ---
saved_view_url = f"http://localhost:9001/{ENTITY}/{PROJECT}?nw=462wyf8o8ac"

workspace = ws.Workspace.from_url(saved_view_url)
print("Loaded:", workspace.name)
print("Original filters:", workspace.runset_settings.filters)

# --- Modify: set new filters with ORs + an AND ---
workspace.runset_settings.filters = (
    'Metric("Name") == "you-belong-with-me"'
    ' or (Metric("Name") == "mine"'
    ' and Metric("State") == "finished" or (Metric("Name") == "exile" or Metric("Name") == "mine") or Metric("Name") == "style")'
)
workspace.name = "new workspace"

print("New filters:", workspace.runset_settings.filters)
workspace.save()
print("Saved!")

# --- Verify what got written ---
api = wandb.Api()
query = gql("""
query Views($entityName: String, $name: String) {
    project(name: $name, entityName: $entityName) {
        allViews(viewType: "project-view") {
            edges {
                node { name displayName spec }
            }
        }
    }
}
""")
response = api.client.execute(query, {"entityName": ENTITY, "name": PROJECT})
edges = response["project"]["allViews"]["edges"]

for e in edges:
    n = e["node"]
    if "OR plus AND" in n["displayName"]:
        spec = json.loads(n["spec"])
        filters = spec["section"]["runSets"][0]["filters"]
        print("\nRaw v2 filters written to backend:")
        print(json.dumps(filters, indent=2))
