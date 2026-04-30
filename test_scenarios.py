"""Manual testing scenarios for v2 filter support.

Run with:
    WANDB_API_KEY=<key> WANDB_BASE_URL=http://localhost:9001 python test_scenarios.py

Prerequisites:
    - Local W&B instance running at localhost:9001
    - A project with some runs (uses ENTITY/PROJECT below)
    - Create a saved view in the UI with v2 filters (OR connectors / groups)
      and paste its URL into V2_WORKSPACE_URL below
"""

import json
import sys
import textwrap

import wandb
import wandb_workspaces.workspaces as ws
from wandb_workspaces import expr
from wandb_workspaces.workspaces.internal import gql

# ── Configuration ──────────────────────────────────────────────────────────────
ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr22"

# Paste the URL of a saved view that has v2 filters (OR connectors / groups)
V2_WORKSPACE_URL = f"http://localhost:9001/{ENTITY}/{PROJECT}?nw=462wyf8o8ac"
# ───────────────────────────────────────────────────────────────────────────────


def banner(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def fetch_backend_filters(display_name):
    """Query the backend for the raw filter JSON of a saved view by name."""
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
    for e in response["project"]["allViews"]["edges"]:
        n = e["node"]
        if n["displayName"] == display_name:
            spec = json.loads(n["spec"])
            return spec["section"]["runSets"][0]["filters"]
    return None


def check(label, condition):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 1: Load and display a v2 workspace (before fix, connectors dropped)
# ══════════════════════════════════════════════════════════════════════════════
def scenario_1_load_v2():
    banner("Scenario 1: Load a v2 workspace and inspect filters")

    workspace = ws.Workspace.from_url(V2_WORKSPACE_URL)
    print(f"  Name:    {workspace.name}")
    print(f"  Filters: {workspace.runset_settings.filters}")
    print(f"  Has raw v2 stash: {workspace._raw_filters_v2 is not None}")

    check("Filters string is not empty", workspace.runset_settings.filters != "")
    check("Raw v2 dict is stashed", workspace._raw_filters_v2 is not None)

    if workspace._raw_filters_v2:
        print(f"\n  Raw v2 dict from backend:")
        print(textwrap.indent(json.dumps(workspace._raw_filters_v2, indent=2), "    "))

    has_or = " or " in workspace.runset_settings.filters.lower()
    check("Filter string contains 'or' (connector preserved)", has_or)

    # Also verify by re-querying the backend directly
    print(f"\n  Verifying backend directly...")
    backend = fetch_backend_filters(workspace.name)
    if backend:
        is_v2 = backend.get("filterFormat") == "filterV2"
        check("Backend stores v2 format", is_v2)
        or_connectors = [f for f in backend.get("filters", []) if f.get("connector") == "OR"]
        groups = [f for f in backend.get("filters", []) if "filters" in f]
        print(f"  OR connectors in backend: {len(or_connectors)}")
        print(f"  Groups in backend: {len(groups)}")
    else:
        print(f"  WARNING: Could not find '{workspace.name}' in backend")

    return workspace


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 2a: Modify v2 workspace filters, save, verify v2 format preserved
# ══════════════════════════════════════════════════════════════════════════════
def scenario_2a_modify_v2():
    banner("Scenario 2a: Modify v2 workspace with new string filters")

    workspace = ws.Workspace.from_url(V2_WORKSPACE_URL)
    original_filters = workspace.runset_settings.filters
    print(f"  Original filters: {original_filters}")
    print(f"  Has raw v2 stash: {workspace._raw_filters_v2 is not None}")
    if workspace._raw_filters_v2:
        print(f"\n  Loaded v2 viewspec filters:")
        print(textwrap.indent(json.dumps(workspace._raw_filters_v2, indent=2), "    "))
    print()

    new_filters = (
        'Metric("Name") == "tolerate-it"'
        ' or (Metric("Name") == "ivy" and Metric("State") == "finished"'
        ' and Metric("Name") == "evermore")'
    )
    workspace.runset_settings.filters = new_filters
    workspace.name = "Scenario 2a - Modified V2"
    print(f"  New:      {workspace.runset_settings.filters}")

    workspace.save()
    print("  Saved!\n")

    backend = fetch_backend_filters("Scenario 2a - Modified V2")
    if backend:
        print("  Backend filters:")
        print(textwrap.indent(json.dumps(backend, indent=2), "    "))
        check("Written as v2 format", backend.get("filterFormat") == "filterV2")
        items = backend.get("filters", [])
        has_or_connector = any(f.get("connector") == "OR" for f in items)
        check("Has OR connectors in v2", has_or_connector)
        has_group = any("filters" in f for f in items)
        check("Has group for (mine AND finished)", has_group)
    else:
        print("  WARNING: Could not find saved view in backend")


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 2b: Groups via parentheses in filter strings
# ══════════════════════════════════════════════════════════════════════════════
def scenario_2b_groups_from_parens():
    banner("Scenario 2b: Verify groups from explicit parentheses")

    test_cases = [
        (
            "Explicit parens: (A or B) and C",
            '(Config("lr") == 0.01 or Config("lr") == 0.1) and Metric("State") == "finished"',
        ),
        (
            "AND precedence creates implicit group: A and B or C",
            'Metric("State") == "finished" and Config("lr") == 0.01 or Config("lr") == 0.1',
        ),
        (
            "Nested parens: A or (B and C or (D or E))",
            'Metric("Name") == "a" or (Metric("Name") == "b" and Metric("State") == "finished"'
            ' or (Metric("Name") == "c" or Metric("Name") == "d"))',
        ),
    ]

    for label, filter_str in test_cases:
        print(f"  --- {label} ---")
        print(f"  Input:  {filter_str}")
        tree = expr.expr_to_filters(filter_str)
        v2 = expr.filters_tree_to_v2(tree)
        result_str = expr.filters_v2_to_string(v2)
        print(f"  Tree:   root.op={tree.op}, children={len(tree.filters or [])}")
        print(f"  V2:     {json.dumps(v2, indent=2)[:200]}...")
        print(f"  String: {result_str}")
        has_group = any("filters" in f for f in v2["filters"])
        check(f"V2 contains a group", has_group)
        print()


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 2c: Save unchanged v2 workspace (raw dict pass-through)
# ══════════════════════════════════════════════════════════════════════════════
def scenario_2c_unchanged_v2():
    banner("Scenario 2c: Save unchanged v2 workspace (raw dict pass-through)")

    workspace = ws.Workspace.from_url(V2_WORKSPACE_URL)
    original_raw = workspace._raw_filters_v2
    print(f"  Filters: {workspace.runset_settings.filters}")
    print(f"  Raw v2 stashed: {original_raw is not None}")

    workspace.name = "Scenario 2c - Unchanged V2"
    workspace.save()
    print("  Saved (filters NOT modified)!\n")

    backend = fetch_backend_filters("Scenario 2c - Unchanged V2")
    if backend:
        print("  Backend filters:")
        print(textwrap.indent(json.dumps(backend, indent=2), "    "))
        check("Written as v2 format", backend.get("filterFormat") == "filterV2")
        check("Raw dict matches original", backend == original_raw)
    else:
        print("  WARNING: Could not find saved view in backend")


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 3: Create a NEW workspace with legacy AND-only filters
# ══════════════════════════════════════════════════════════════════════════════
def scenario_3_new_legacy():
    banner("Scenario 3: Create new workspace with legacy filters")

    workspace = ws.Workspace(
        entity=ENTITY,
        project=PROJECT,
        name="Scenario 3 - Legacy Filters",
        runset_settings=ws.RunsetSettings(
            filters='Config("lr") == 0.01 and Metric("State") == "finished"',
        ),
    )
    print(f"  Filters: {workspace.runset_settings.filters}")
    print(f"  Has raw v2: {workspace._raw_filters_v2 is not None}")
    check("No raw v2 stash (fresh workspace)", workspace._raw_filters_v2 is None)

    workspace.save()
    print("  Saved!\n")

    backend = fetch_backend_filters("Scenario 3 - Legacy Filters")
    if backend:
        print("  Backend filters:")
        print(textwrap.indent(json.dumps(backend, indent=2), "    "))
        is_legacy = backend.get("op") in ("OR", "AND")
        is_v2 = backend.get("filterFormat") == "filterV2"
        check("Written as legacy tree (not v2)", is_legacy and not is_v2)
        print("\n  NOTE: The UI will convert this to v2 format on next edit.")
    else:
        print("  WARNING: Could not find saved view in backend")


# ══════════════════════════════════════════════════════════════════════════════
# Scenario 4: V2 flag OFF — verify legacy behavior unchanged
# ══════════════════════════════════════════════════════════════════════════════
def scenario_4_legacy_roundtrip():
    banner("Scenario 4: Legacy workspace round-trip (v2 flag OFF)")
    print("  This tests that loading/saving a legacy workspace still works.")
    print("  Use a workspace that does NOT have v2 filters.\n")

    workspace = ws.Workspace(
        entity=ENTITY,
        project=PROJECT,
        name="Scenario 4 - Legacy Roundtrip",
        runset_settings=ws.RunsetSettings(
            filters='Config("lr") == 0.01 and Metric("State") == "finished"',
        ),
    )

    check("No raw v2 stash", workspace._raw_filters_v2 is None)

    workspace.save()
    print("  Saved!\n")

    # Reload it
    backend = fetch_backend_filters("Scenario 4 - Legacy Roundtrip")
    if backend:
        print("  Backend filters:")
        print(textwrap.indent(json.dumps(backend, indent=2), "    "))
        is_legacy = backend.get("op") in ("OR", "AND")
        check("Still legacy format after save", is_legacy)

        # Simulate loading from backend (parse the tree back to string)
        filter_string = expr.filters_v2_to_string(
            expr.filters_tree_to_v2(expr.Filters.model_validate(backend))
        )
        print(f"\n  Re-parsed string: {filter_string}")
        check("Round-trip string contains expected values",
               "0.01" in filter_string and "finished" in filter_string)
    else:
        print("  WARNING: Could not find saved view in backend")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════
SCENARIOS = {
    "1":  ("Load v2 workspace", scenario_1_load_v2),
    "2a": ("Modify v2 workspace", scenario_2a_modify_v2),
    # "2b": ("Groups from parentheses (offline)", scenario_2b_groups_from_parens),
    # "2c": ("Unchanged v2 pass-through", scenario_2c_unchanged_v2),
    # "3":  ("New workspace with legacy filters", scenario_3_new_legacy),
    # "4":  ("Legacy round-trip (v2 flag OFF)", scenario_4_legacy_roundtrip),
}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        keys = sys.argv[1:]
    else:
        print("Usage: python test_scenarios.py [scenario_ids...]")
        print("       python test_scenarios.py all")
        print()
        for k, (desc, _) in SCENARIOS.items():
            print(f"  {k:4s}  {desc}")
        print()
        sys.exit(0)

    if "all" in keys:
        keys = list(SCENARIOS.keys())

    for k in keys:
        if k not in SCENARIOS:
            print(f"Unknown scenario: {k}")
            continue
        _, fn = SCENARIOS[k]
        fn()

    print(f"\n{'=' * 70}")
    print("  Done!")
    print(f"{'=' * 70}")
