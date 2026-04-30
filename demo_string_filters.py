"""Demo: string filters with ANDs, ORs, and parenthesised groups.

Creates workspaces using string-based filters and verifies the v2 dict
written to the backend has the correct connectors and groups.

Run with:
    WANDB_API_KEY=<key> WANDB_BASE_URL=http://localhost:9001 python demo_string_filters.py
"""

import json

import wandb_workspaces.workspaces as ws
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


def describe_v2(raw):
    """Print a summary of the v2 dict structure."""
    filters_list = raw.get("filters", [])
    for i, item in enumerate(filters_list):
        if "filters" in item:
            inner = item["filters"]
            inner_desc = ", ".join(
                f"{f.get('key', {}).get('name')} {f.get('connector', '-')}"
                for f in inner
            )
            print(f"  [{i}] GROUP (connector={item.get('connector')}): [{inner_desc}]")
        else:
            print(f"  [{i}] {item.get('key', {}).get('name')} {item.get('op')} {item.get('value')!r}  connector={item.get('connector')}")


# ─── 1. Simple AND ───────────────────────────────────────────────────────────

# banner("1. Simple AND: A and B")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-str-and",
#     runset_settings=ws.RunsetSettings(
#         filters="Metric('Name') == 'folklore' and Metric('State') == 'finished'"
#     ),
# )
# print(f"Filters string: {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")
# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)
# describe_v2(raw)


# ─── 2. Simple OR ────────────────────────────────────────────────────────────

# banner("2. Simple OR: A or B")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-str-or",
#     runset_settings=ws.RunsetSettings(
#         filters="Metric('Name') == 'folklore' or Metric('Name') == 'evermore'"
#     ),
# )
# print(f"Filters string: {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")
# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)
# describe_v2(raw)


# ─── 3. A or B and C (no parens — AND binds tighter, no group) ───────────────

banner("3. A or B and C — no parens, AND binds tighter, no group needed")

workspace = ws.Workspace(
    entity=ENTITY,
    project=PROJECT,
    name="demo-str-or-and-flat",
    runset_settings=ws.RunsetSettings(
        filters="Metric('Name') == 'folklore' or (Metric('Name') == 'evermore' or Metric('Name') == 'exile' or Metric('Name') == 'evermore' and Metric('State') == 'finished')"
    ),
)
print(f"Filters string: {workspace.runset_settings.filters!r}")

url = workspace.save()
print(f"Saved: {url}")
view_name = url.split("nw=")[-1]
raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
dump("Backend v2 dict", raw)
describe_v2(raw)


# # ─── 4. A and (B or C) — explicit parens → group ────────────────────────────

# banner("4. A and (B or C) — explicit parens create a group")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-str-and-group",
#     runset_settings=ws.RunsetSettings(
#         filters="Metric('Name') == 'folklore' and (Metric('Name') == 'evermore' or Metric('State') == 'finished')"
#     ),
# )
# print(f"Filters string: {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")
# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)
# describe_v2(raw)


# # ─── 5. A or B and (C or D) — mixed with one group ──────────────────────────

# banner("5. A or B and (C or D) — group only for the parens")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-str-mixed-group",
#     runset_settings=ws.RunsetSettings(
#         filters="Metric('Name') == 'folklore' or Metric('Name') == 'evermore' and (Metric('State') == 'finished' or Metric('Name') == 'exile')"
#     ),
# )
# print(f"Filters string: {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")
# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)
# describe_v2(raw)


# # ─── 6. (A and B) or (C and D) — AND inside OR, no groups needed ─────────────

# banner("6. (A and B) or (C and D) — AND inside OR, no groups needed")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-str-and-in-or",
#     runset_settings=ws.RunsetSettings(
#         filters="(Metric('Name') == 'folklore' and Metric('State') == 'finished') or (Metric('Name') == 'evermore' and Metric('State') == 'crashed')"
#     ),
# )
# print(f"Filters string: {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")
# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)
# describe_v2(raw)


# # ─── 7. (A or B) and (C or D) — both ORs inside AND → two groups ────────────

# banner("7. (A or B) and (C or D) — two groups")

# workspace = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="demo-str-two-groups",
#     runset_settings=ws.RunsetSettings(
#         filters="(Metric('Name') == 'folklore' or Metric('Name') == 'evermore') and (Metric('State') == 'finished' or Metric('Name') == 'exile')"
#     ),
# )
# print(f"Filters string: {workspace.runset_settings.filters!r}")

# url = workspace.save()
# print(f"Saved: {url}")
# view_name = url.split("nw=")[-1]
# raw = fetch_raw_filters(ENTITY, PROJECT, view_name)
# dump("Backend v2 dict", raw)
# describe_v2(raw)


# banner("Done!")
