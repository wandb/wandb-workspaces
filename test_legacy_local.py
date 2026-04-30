import json

import wandb
import wandb_workspaces.workspaces as ws
from wandb_workspaces import expr
from wandb_workspaces.workspaces.internal import gql

ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr22"

# --- Create a fresh workspace with legacy AND-only filters ---
workspace = ws.Workspace(
    entity=ENTITY,
    project=PROJECT,
    name="Legacy Filter Test",
    runset_settings=ws.RunsetSettings(
        filters='Config("lr") == 0.01 and Metric("State") == "finished"',
    ),
)

print("Filters:", workspace.runset_settings.filters)
print("Has raw v2:", workspace._raw_filters_v2 is not None)
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
    if n["displayName"] == "Legacy Filter Test":
        spec = json.loads(n["spec"])
        filters = spec["section"]["runSets"][0]["filters"]
        print("\nRaw filters written to backend:")
        print(json.dumps(filters, indent=2))

        # Check structure: should be OR -> AND -> leaves
        if filters.get("op") == "OR" and filters.get("filters"):
            and_node = filters["filters"][0]
            if and_node.get("op") == "AND":
                print("\nLegacy shape OK: OR -> AND -> leaves")
            else:
                print("\nWARNING: Expected AND node, got:", and_node.get("op"))
        else:
            print("\nWARNING: Root is not OR, got:", filters.get("op", filters.get("filterFormat", "unknown")))
