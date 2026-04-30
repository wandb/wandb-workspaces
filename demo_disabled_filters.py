"""Test script: disabled filter handling on feat/v2-filters-workspace-write.

Loads a workspace with disabled legacy filters and checks:
1. What the raw backend filters look like
2. What string the SDK shows the user
3. What _to_model produces (unchanged)
4. What the backend looks like after unchanged save
5. What the backend looks like after modified save
"""

import json
import os
os.environ["WANDB_BASE_URL"] = "http://localhost:9001"

import wandb_workspaces.workspaces as ws
from wandb_workspaces.workspaces import internal
from wandb_workspaces import expr

URL = "http://localhost:9001/marie-barrramsey-wb/taylor-pr23?nw=2hsd1f6yjec"


def print_section(title):
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}")


def get_raw_filters(entity, project, view_name):
    """Fetch raw filters dict from the backend."""
    view_dict = internal.get_view_dict(entity, project, view_name)
    spec = json.loads(view_dict["spec"]) if isinstance(view_dict["spec"], str) else view_dict["spec"]
    return spec.get("section", {}).get("runSets", [{}])[0].get("filters", {})


def describe_filters(raw):
    """Print a summary of a raw filter dict (works for both legacy and v2)."""
    is_v2 = isinstance(raw, dict) and raw.get("filterFormat") == "filterV2"
    print(f"  Format: {'v2' if is_v2 else 'legacy'}")
    if is_v2:
        items = raw.get("filters", [])
        print(f"  Total items: {len(items)}")
        for i, f in enumerate(items):
            status = "DISABLED" if f.get("disabled") else "active"
            connector = f.get("connector", "(none)")
            key = f.get("key", {}).get("name", "GROUP") if "key" in f else "GROUP"
            print(f"    [{i}] {key} connector={connector} {status}")
    else:
        def walk(node, depth=0):
            indent = "    " * (depth + 1)
            op = node.get("op", "?")
            if node.get("filters"):
                disabled = node.get("disabled")
                dis_str = f" DISABLED" if disabled else ""
                print(f"{indent}{op}{dis_str} (children: {len(node['filters'])})")
                for child in node["filters"]:
                    walk(child, depth + 1)
            elif node.get("key"):
                val = node.get("value", "?")
                disabled = node.get("disabled", False)
                dis_str = " DISABLED" if disabled else ""
                name = node["key"].get("name", "?")
                print(f"{indent}{name} {op} {val!r}{dis_str}")
        walk(raw)


# ── Step 0: Reset workspace to clean legacy state ─────────────────────
# print_section("Step 0: Resetting workspace to clean state")

# workspace_reset = ws.Workspace.from_url(URL)
# workspace_reset.runset_settings.filters = 'Metric("Name") == \'we-are-never-getting-back-together\''
# workspace_reset.save()
# print("  Saved clean single-filter workspace")

# # Now manually add the disabled filter via raw spec manipulation
# # to get a clean: OR → AND → [wangbt(active), love-story(disabled)]
# view_name = internal._internal_name_to_url_query_str(workspace_reset._internal_name)
# raw_reset = get_raw_filters(workspace_reset.entity, workspace_reset.project, view_name)
# print("  After reset:")
# print(json.dumps(raw_reset, indent=2))

view_name = "2hsd1f6yjec"
# ── Step 1: Read raw backend filters ──────────────────────────────────
print_section("Step 1: Raw backend filters (clean state)")

workspace = ws.Workspace.from_url(URL)
raw = get_raw_filters(workspace.entity, workspace.project, view_name)
print(json.dumps(raw, indent=2))
describe_filters(raw)


# ── Step 2: What the SDK shows the user ───────────────────────────────
print_section("Step 2: SDK filter string (what user sees)")
print(f"  filters = {workspace.runset_settings.filters!r}")
print(f"  _raw_filters_v2 = {getattr(workspace, '_raw_filters_v2', None) is not None}")


# ── Step 3: _to_model output (unchanged) ─────────────────────────────
print_section("Step 3: _to_model output (unchanged filters)")
model = workspace._to_model()
filters_out = model.spec.section.run_sets[0].filters

if isinstance(filters_out, dict):
    print("Output format: v2 dict")
    print(json.dumps(filters_out, indent=2))
else:
    print("Output format: legacy Filters tree")
    print(filters_out.model_dump_json(indent=2, exclude_none=True))
describe_filters(
    filters_out if isinstance(filters_out, dict)
    else json.loads(filters_out.model_dump_json(exclude_none=True))
)


# ── Step 4: Actually save unchanged, then re-read from backend ────────
print_section("Step 4: Save unchanged → re-read from backend")

workspace3 = ws.Workspace.from_url(URL)
workspace3.save()

raw_after_save = get_raw_filters(workspace3.entity, workspace3.project, view_name)
print("Backend filters after unchanged save:")
print(json.dumps(raw_after_save, indent=2))
describe_filters(raw_after_save)


# ── Step 5: Modify filters, save, then re-read from backend ──────────
print_section("Step 5: Modify filters → save → re-read from backend")

workspace4 = ws.Workspace.from_url(URL)
original_filters = workspace4.runset_settings.filters
workspace4.runset_settings.filters = original_filters + " and Config('lr') == 0.01"
print(f"  Modified filters: {workspace4.runset_settings.filters!r}")

# Show what _to_model will produce before saving
model4 = workspace4._to_model()
filters_out4 = model4.spec.section.run_sets[0].filters
print("\n  _to_model output (before save):")
if isinstance(filters_out4, dict):
    print(json.dumps(filters_out4, indent=2))
else:
    print(filters_out4.model_dump_json(indent=2, exclude_none=True))

workspace4.save()

raw_after_modify = get_raw_filters(workspace4.entity, workspace4.project, view_name)
print("\nBackend filters after modified save:")
print(json.dumps(raw_after_modify, indent=2))
describe_filters(raw_after_modify)


# ── Summary ───────────────────────────────────────────────────────────
print_section("Summary")
is_v2_original = isinstance(raw, dict) and raw.get("filterFormat") == "filterV2"
is_v2_after_save = isinstance(raw_after_save, dict) and raw_after_save.get("filterFormat") == "filterV2"
print(f"  Original format:     {'v2' if is_v2_original else 'legacy'}")
print(f"  After save format:   {'v2' if is_v2_after_save else 'legacy'}")
print(f"  Filters match (step1 vs step4): {json.dumps(raw) == json.dumps(raw_after_save)}")
