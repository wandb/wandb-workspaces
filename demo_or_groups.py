"""Demo: Or / And / Group programmatic filter API.

Tests the new object-based filter construction on feat/v2-filters-or-groups.
Creates workspaces with Or, And, and Group filters and verifies the v2 dict
written to the backend preserves connectors and nested groups.

Run with:
    WANDB_API_KEY=<key> WANDB_BASE_URL=http://localhost:9001 python demo_or_groups.py
"""

import json

import wandb_workspaces.workspaces as ws
from wandb_workspaces.workspaces import internal
from wandb_workspaces.workspaces.internal import gql

ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr22"


def banner(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def fetch_raw_filters(entity, project, view_name):
    """Fetch the raw filters dict from the backend via GraphQL."""
    api = gql.WandbAPI()
    data = api.viewer_default_entity_view(entity, project, view_name)
    spec = json.loads(data["spec"])
    return spec["section"]["runSets"][0]["filters"]


def dump(label, obj):
    print(f"{label}:")
    print(json.dumps(obj, indent=2))
    print()


# # ─── Scenario 1: Simple AND ──────────────────────────────────────────────────

# banner("Scenario 1: Simple AND — two conditions ANDed together")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-or-groups-and",
#     runset_settings=ws.RunsetSettings(
#         filters=ws.And(
#             ws.Metric("Name") == "folklore",
#             ws.Metric("State") == "finished",
#         )
#     ),
# )

# print(f"SDK filters (normalized to string): {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")

# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)

# has_v2 = raw.get("filterFormat") == "filterV2"
# print(f"Written as v2? {has_v2}")
# if has_v2:
#     connectors = [f.get("connector") for f in raw["filters"] if isinstance(f, dict) and "key" in f]
#     print(f"Connectors: {connectors}")


# # ─── Scenario 2: Simple OR ───────────────────────────────────────────────────

# banner("Scenario 2: Simple OR — two conditions ORed together")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-or-groups-or",
#     runset_settings=ws.RunsetSettings(
#         filters=ws.Or(
#             ws.Metric("Name") == "folklore",
#             ws.Metric("Name") == "evermore",
#         )
#     ),
# )

# print(f"SDK filters (normalized to string): {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")

# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)

# has_v2 = raw.get("filterFormat") == "filterV2"
# print(f"Written as v2? {has_v2}")
# if has_v2:
#     connectors = [f.get("connector") for f in raw["filters"] if isinstance(f, dict) and "key" in f]
#     print(f"Connectors: {connectors}")


# # ─── Scenario 3: Mixed OR + AND ──────────────────────────────────────────────

# banner("Scenario 3: Mixed — folklore OR (evermore AND finished)")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-or-groups-mixed",
#     runset_settings=ws.RunsetSettings(
#         filters=ws.Or(
#             ws.Metric("Name") == "folklore",
#             ws.And(
#                 ws.Metric("Name") == "evermore",
#                 ws.Metric("State") == "finished",
#             ),
#         )
#     ),
# )

# print(f"SDK filters (normalized to string): {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")

# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)

# has_v2 = raw.get("filterFormat") == "filterV2"
# print(f"Written as v2? {has_v2}")
# if has_v2:
#     connectors = [f.get("connector") for f in raw["filters"] if isinstance(f, dict) and "key" in f]
#     print(f"Connectors: {connectors}")


# ─── Scenario 4: Nested groups with Group() ──────────────────────────────────

banner("Scenario 4: Nested groups — folklore OR evermore AND (finished OR exile)")

workspace = ws.Workspace(
    entity=ENTITY,
    project=PROJECT,
    name="demo-or-groups-nested",
    runset_settings=ws.RunsetSettings(
        filters=ws.Or(
            ws.Metric("Name") == "folklore",
            ws.And(
                ws.Metric("Name") == "evermore",
                ws.Group(
                    ws.Or(
                        ws.Metric("State") == "finished",
                        ws.Metric("Name") == "exile",
                    )
                ),
            ),
        )
    ),
)

print(f"SDK filters (normalized to string): {workspace.runset_settings.filters!r}")

url = workspace.save()
print(f"Saved: {url}")

view_name = url.split("nw=")[-1]
raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
dump("Backend v2 dict", raw)

has_v2 = raw.get("filterFormat") == "filterV2"
print(f"Written as v2? {has_v2}")
if has_v2:
    for i, item in enumerate(raw["filters"]):
        if "filters" in item:
            print(f"  Item {i} is a GROUP with {len(item['filters'])} children, connector={item.get('connector')}")
        else:
            print(f"  Item {i}: {item.get('key', {}).get('name')} {item.get('op')} {item.get('value')}, connector={item.get('connector')}")


# # ─── Scenario 5: Read back a saved workspace ─────────────────────────────────

# banner("Scenario 5: Read back Scenario 4 and verify filter string")

# loaded = ws.Workspace.from_url(url)
# print(f"Loaded filters: {loaded.runset_settings.filters!r}")

# print()
# print("Expected: Metric(\"Name\") == 'folklore' or Metric(\"Name\") == 'evermore' and (Metric(\"State\") == 'finished' or Metric(\"Name\") == 'exile')")

# ─── Scenario 6: Load, modify, and re-save ───────────────────────────────────

# banner("Scenario 6: Load Scenario 4, change filters with Or/And, re-save")

# loaded = ws.Workspace.from_url(url)
# print(f"Original filters: {loaded.runset_settings.filters!r}")

# loaded.runset_settings.filters = ws.Or(
#     ws.Metric("Name") == "willow",
#     ws.And(
#         ws.Metric("State") == "finished",
#         ws.Group(
#             ws.Or(
#                 ws.Metric("Name") == "cardigan",
#                 ws.Metric("Name") == "betty",
#             )
#         ),
#     ),
# )
# print(f"New filters:      {loaded.runset_settings.filters!r}")

# url2 = loaded.save()
# print(f"Saved: {url2}")

# view_name2 = url2.split("nw=")[-1]
# raw2 = fetch_raw_filters(ENTITY, PROJECT, view_name2)
# dump("Backend v2 dict after modify", raw2)

# has_v2 = raw2.get("filterFormat") == "filterV2"
# print(f"Written as v2? {has_v2}")
# if has_v2:
#     for i, item in enumerate(raw2["filters"]):
#         if "filters" in item:
#             print(f"  Item {i} is a GROUP with {len(item['filters'])} children, connector={item.get('connector')}")
#         else:
#             print(f"  Item {i}: {item.get('key', {}).get('name')} {item.get('op')} {item.get('value')}, connector={item.get('connector')}")

# reloaded = ws.Workspace.from_url(url2)
# print(f"\nRead back: {reloaded.runset_settings.filters!r}")
# print("Expected: Metric(\"Name\") == 'willow' or Metric(\"State\") == 'finished' and (Metric(\"Name\") == 'cardigan' or Metric(\"Name\") == 'betty')")

# banner("Done!")
