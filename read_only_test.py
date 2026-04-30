"""Inspect workspace filters: read current state, then test string and object writes."""

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


def show_filters(label, raw):
    """Print filters in a compact tree format."""
    print(f"\n=== {label} ===")
    print(json.dumps(raw, indent=2))


# ── 1. Current state ─────────────────────────────────────────────────
workspace = ws.Workspace.from_url(URL)
raw = get_raw_filters(workspace.entity, workspace.project)

print("=== 1. Current backend filters ===")
print(json.dumps(raw, indent=2))

print("\n=== 1b. SDK filter string ===")
print(repr(workspace.runset_settings.filters))


# ── 2. Modify using string (append) ──────────────────────────────────
print("\n" + "=" * 60)
print("  2. String modification: append ' and Config(\"lr\") == 0.01'")
print("=" * 60)

ws2 = ws.Workspace.from_url(URL)
ws2.runset_settings.filters = ws2.runset_settings.filters + " and Config('lr') == 0.01"
print(f"  New string: {ws2.runset_settings.filters!r}")

model2 = ws2._to_model()
f2 = model2.spec.section.run_sets[0].filters
print("\n  _to_model output:")
if isinstance(f2, dict):
    print(json.dumps(f2, indent=2))
else:
    print(f2.model_dump_json(indent=2, exclude_none=True))

ws2.save()
show_filters("2b. Backend after string save", get_raw_filters(ws2.entity, ws2.project))


# # ── 3. Restore clean state, then modify using object (FilterExpr list)
# print("\n" + "=" * 60)
# print("  3. Restore, then object modification: FilterExpr list")
# print("=" * 60)

# ws3 = ws.Workspace.from_url(URL)
# ws3.runset_settings.filters = [
#     expr.Metric("Name") == "we-are-never-getting-back-together",
#     expr.Metric("Name") == "tolerate-it",
#     expr.Metric("Name") == "love-story",
#     expr.Config("lr") == 0.01,
# ]
# print(f"  Filters set as list of FilterExpr objects")
# print(f"  After validator, string: {ws3.runset_settings.filters!r}")

# model3 = ws3._to_model()
# f3 = model3.spec.section.run_sets[0].filters
# print("\n  _to_model output:")
# if isinstance(f3, dict):
#     print(json.dumps(f3, indent=2))
# else:
#     print(f3.model_dump_json(indent=2, exclude_none=True))

# ws3.save()
# show_filters("3b. Backend after object save", get_raw_filters(ws3.entity, ws3.project))
