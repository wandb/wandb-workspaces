"""End-to-end test for v2 filter read/write round-trip against local server.

Usage:
    WANDB_ENTITY=marie-barrramsey-wb WANDB_PROJECT=taylor-pr23 \
        WANDB_BASE_URL=http://localhost:9001 \
        .venv-test2/bin/python test_v2_e2e.py
"""

import json
import os
import sys

os.environ.setdefault("WANDB_BASE_URL", "http://localhost:9001")

import wandb
import wandb_workspaces.workspaces as ws
from wandb_workspaces.expr import is_filter_v2
from wandb_workspaces.workspaces.internal import (
    _internal_name_to_url_query_str,
    get_view_dict,
)

ENTITY = os.environ.get("WANDB_ENTITY", "marie-barrramsey-wb")
PROJECT = os.environ.get("WANDB_PROJECT", "taylor-pr23")

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
INFO = "\033[94mINFO\033[0m"

results = []


def check(name, condition, detail=""):
    """Record a test result."""
    status = PASS if condition else FAIL
    results.append((name, condition))
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))


def get_raw_filters(workspace):
    """Fetch the raw filters dict from the backend for a saved workspace."""
    nw = _internal_name_to_url_query_str(workspace._internal_name)
    view_dict = get_view_dict(ENTITY, PROJECT, nw)
    spec = json.loads(view_dict["spec"])
    return spec.get("section", {}).get("runSets", [{}])[0].get("filters", {})


# ── Test 1: AND-only workspace → stays in legacy format ──

print(f"\n{'='*70}")
print("Test 1: AND-only workspace → should stay in legacy format")
print(f"{'='*70}")

workspace_and = ws.Workspace(
    name="[E2E Test] AND-Only Filters",
    entity=ENTITY,
    project=PROJECT,
    sections=[ws.Section(name="Results", panels=[], is_open=True)],
    runset_settings=ws.RunsetSettings(
        filters="Config('learning_rate') == 0.001 and Metric('State') == 'finished'"
    ),
)
workspace_and.save()
url_and = workspace_and.url
print(f"  [{INFO}] Saved AND-only workspace: {url_and}")

ws_loaded = ws.Workspace.from_url(url_and)
filter_str = ws_loaded.runset_settings.filters
print(f"  [{INFO}] Loaded filters string: {filter_str!r}")

check("AND filters loaded back", "learning_rate" in filter_str and "finished" in filter_str)
check("No raw v2 stashed", ws_loaded._raw_filters_v2 is None)

ws_loaded.save()

raw = get_raw_filters(ws_loaded)
check("AND workspace stored in legacy format", not is_filter_v2(raw))


# ── Test 2: Create v2 workspace via GraphQL injection, load and round-trip ──

print(f"\n{'='*70}")
print("Test 2: V2 workspace with OR → load, verify, re-save, verify format preserved")
print(f"{'='*70}")

from wandb_gql import gql

ws_seed = ws.Workspace(
    name="[E2E Test] V2 Filters with OR",
    entity=ENTITY,
    project=PROJECT,
    sections=[ws.Section(name="Results", panels=[], is_open=True)],
    runset_settings=ws.RunsetSettings(filters="Config('learning_rate') == 0.001"),
)
ws_seed.save()
seed_name = ws_seed._internal_name
seed_id = ws_seed._internal_id
print(f"  [{INFO}] Created seed workspace: {ws_seed.url}")

seed_nw = _internal_name_to_url_query_str(seed_name)
seed_view = get_view_dict(ENTITY, PROJECT, seed_nw)
seed_spec = json.loads(seed_view["spec"])

v2_filters = {
    "filterFormat": "filterV2",
    "filters": [
        {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
        {"op": "=", "key": {"section": "config", "name": "learning_rate"}, "value": 0.001, "disabled": False, "connector": "AND"},
        {"op": "=", "key": {"section": "config", "name": "learning_rate"}, "value": 0.01, "disabled": False, "connector": "OR"},
    ],
}
for rs_item in seed_spec.get("section", {}).get("runSets", []):
    rs_item["filters"] = v2_filters

api = wandb.Api()
update_query = gql("""
    mutation UpsertView2($id: ID, $entityName: String, $projectName: String, $type: String, $name: String, $displayName: String, $description: String, $spec: String) {
        upsertView(input: {id: $id, entityName: $entityName, projectName: $projectName, name: $name, displayName: $displayName, description: $description, type: $type, spec: $spec, createdUsing: WANDB_SDK}) {
            view { id name }
            inserted
        }
    }
""")
api.client.execute(update_query, variable_values={
    "id": seed_id,
    "entityName": ENTITY,
    "projectName": PROJECT,
    "name": seed_name,
    "displayName": "[E2E Test] V2 Filters with OR",
    "type": "project-view",
    "description": "",
    "spec": json.dumps(seed_spec),
})
v2_url = ws_seed.url
print(f"  [{INFO}] Injected v2 filters into workspace: {v2_url}")

# Load the v2 workspace
ws_v2 = ws.Workspace.from_url(v2_url)
filter_str_v2 = ws_v2.runset_settings.filters
print(f"  [{INFO}] Loaded v2 filters string: {filter_str_v2!r}")

check("V2 filters loaded successfully", len(filter_str_v2) > 0)
check("Raw v2 dict stashed", ws_v2._raw_filters_v2 is not None)
check("OR preserved in filter string", "or" in filter_str_v2.lower(), f"filters={filter_str_v2!r}")
check("AND preserved in filter string", "and" in filter_str_v2.lower())

# Re-save without modification
ws_v2.save()
print(f"  [{INFO}] Re-saved v2 workspace")

raw_v2 = get_raw_filters(ws_v2)
print(f"  [{INFO}] Raw filters after save: {json.dumps(raw_v2, indent=2)[:500]}")

check("V2 format preserved after re-save", is_filter_v2(raw_v2))
has_or = any(
    item.get("connector") == "OR"
    for item in raw_v2.get("filters", [])
    if isinstance(item, dict)
)
check("OR connectors preserved in saved v2", has_or)


# ── Test 3: Load v2 workspace, modify filters, re-save → should stay v2 ──

print(f"\n{'='*70}")
print("Test 3: Modify v2 workspace filters → should write back in v2 format")
print(f"{'='*70}")

ws_v2_modified = ws.Workspace.from_url(v2_url)
check("V2 stash present before modification", ws_v2_modified._raw_filters_v2 is not None)

ws_v2_modified.runset_settings.filters = "Config('learning_rate') == 0.002"
ws_v2_modified.save()
print(f"  [{INFO}] Saved with modified filters")

raw_modified = get_raw_filters(ws_v2_modified)
print(f"  [{INFO}] Raw filters after modified save: {json.dumps(raw_modified, indent=2)[:500]}")

check("Modified v2 workspace still in v2 format", is_filter_v2(raw_modified))
check("Modified filter value present", any(
    item.get("value") == 0.002
    for item in raw_modified.get("filters", [])
    if isinstance(item, dict)
))


# ── Summary ──

print(f"\n{'='*70}")
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"Results: {passed} passed, {failed} failed out of {len(results)} checks")
print(f"{'='*70}")

if failed:
    sys.exit(1)
