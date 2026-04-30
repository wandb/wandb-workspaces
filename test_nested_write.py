"""Test what writing a nested filter string does to the workspace across multiple saves."""

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


def count_depth(node, depth=0):
    """Count maximum nesting depth of a filter tree dict."""
    if not isinstance(node, dict):
        return depth
    children = node.get("filters", [])
    if not isinstance(children, list) or not children:
        return depth
    return max(count_depth(c, depth + 1) for c in children)


def print_separator(title):
    """Print a section separator."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


# ── 0. Show current state ────────────────────────────────────────────
workspace = ws.Workspace.from_url(URL)
raw = get_raw_filters(workspace.entity, workspace.project)
print_separator("0. Current state")
print(f"  SDK string: {workspace.runset_settings.filters!r}")
print(f"  Backend depth: {count_depth(raw)}")
print(json.dumps(raw, indent=2))


# ── 1. Write a nested string filter: (a and b) and c ─────────────────
print_separator("1. Write nested string: (a and b) and c")

ws1 = ws.Workspace.from_url(URL)
ws1.runset_settings.filters = "Metric('Name') == 'a' and (Metric('Name') == 'b' or (Config('lr') == 0.01 and (Metric('State') == 'finished' or Config('epochs') == 10)))"
print(f"  Filter string set: {ws1.runset_settings.filters!r}")

ws1.save()
raw1 = get_raw_filters(ws1.entity, ws1.project)
print(f"  Backend depth after save: {count_depth(raw1)}")
print(json.dumps(raw1, indent=2))


# # ── 2. Read back and append, simulating the round-trip bug ────────────
# print_separator("2. Read back + append ' and Config(\"epochs\") == 10'")

# ws2 = ws.Workspace.from_url(URL)
# print(f"  SDK reads back string: {ws2.runset_settings.filters!r}")
# ws2.runset_settings.filters = ws2.runset_settings.filters + " and Config('epochs') == 10"
# print(f"  Modified string: {ws2.runset_settings.filters!r}")

# ws2.save()
# raw2 = get_raw_filters(ws2.entity, ws2.project)
# print(f"  Backend depth after save: {count_depth(raw2)}")
# print(json.dumps(raw2, indent=2))


# # ── 3. One more round-trip ────────────────────────────────────────────
# print_separator("3. Read back + append ' and Config(\"batch_size\") == 32'")

# ws3 = ws.Workspace.from_url(URL)
# print(f"  SDK reads back string: {ws3.runset_settings.filters!r}")
# ws3.runset_settings.filters = ws3.runset_settings.filters + " and Config('batch_size') == 32"
# print(f"  Modified string: {ws3.runset_settings.filters!r}")

# ws3.save()
# raw3 = get_raw_filters(ws3.entity, ws3.project)
# print(f"  Backend depth after save: {count_depth(raw3)}")
# print(json.dumps(raw3, indent=2))


# ── Summary ───────────────────────────────────────────────────────────
print_separator("Summary: nesting depth across rounds")
print(f"  Round 0 (before): {count_depth(raw)}")
print(f"  Round 1 (nested write): {count_depth(raw1)}")
print(f"  Round 2 (append): {count_depth(raw2)}")
print(f"  Round 3 (append): {count_depth(raw3)}")
