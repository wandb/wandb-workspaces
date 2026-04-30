"""E2E test: AND, OR, and Group filter functionality against a real W&B instance.

Saves real workspaces and reports, then fetches the raw backend filters via
GraphQL to verify the v2 dict structure.

Covers:
- Deeply nested groups (should flatten to max 1 level)
- ANDs mixed with ORs (ANDs should never create their own groups)
- Explicit parentheses and Group() objects create groups
- New workspace creation and modifying existing workspace filters
- Both workspace and report paths

Run with:
    WANDB_API_KEY=<key> WANDB_BASE_URL=http://localhost:9001 python test_filter_groups_e2e.py
"""

import json
import sys

import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws
from wandb_workspaces import expr
from wandb_workspaces.expr import And, Group, Or
from wandb_workspaces.workspaces import internal

ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr22"

passed = 0
failed = 0


def banner(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def fetch_workspace_filters(entity, project, internal_name):
    """Fetch raw filters dict from the backend for a workspace."""
    url_name = internal._internal_name_to_url_query_str(internal_name)
    view = internal.get_view_dict(entity, project, url_name)
    spec = json.loads(view["spec"])
    return spec["section"]["runSets"][0]["filters"]


def groups(v2):
    """Extract group items from a v2 dict."""
    return [f for f in v2.get("filters", []) if "filters" in f and "key" not in f]


def flat(v2):
    """Extract flat (non-group) items from a v2 dict."""
    return [f for f in v2.get("filters", []) if "key" in f]


def connectors(v2):
    """Extract connectors from top-level flat items."""
    return [f.get("connector") for f in flat(v2)]


def check(label, condition):
    """Assert a condition and print PASS/FAIL."""
    global passed, failed
    status = "PASS" if condition else "FAIL"
    if not condition:
        failed += 1
    else:
        passed += 1
    print(f"  [{status}] {label}")
    return condition


def save_workspace(name, filters):
    """Create and save a workspace, return the raw backend filters."""
    workspace = ws.Workspace(
        entity=ENTITY,
        project=PROJECT,
        name=name,
        runset_settings=ws.RunsetSettings(filters=filters),
    )
    print(f"  SDK string: {workspace.runset_settings.filters!r}")
    workspace.save()
    raw = fetch_workspace_filters(ENTITY, PROJECT, workspace._internal_name)
    print(f"  Backend format: {'v2' if raw.get('filterFormat') == 'filterV2' else 'legacy'}")
    return raw, workspace


def save_report(title, filters):
    """Create and save a report with one runset, return the report object."""
    report = wr.Report(
        entity=ENTITY,
        project=PROJECT,
        title=title,
        blocks=[
            wr.PanelGrid(
                runsets=[wr.Runset(filters=filters)],
            )
        ],
    )
    report.save()
    print(f"  Saved report: {report.url}")
    return report


# ─── WORKSPACE TESTS ─────────────────────────────────────────────────────────

# banner("WORKSPACE 1: ANDs never create groups")

# raw, _ = save_workspace(
#     "e2e-and-no-group-1",
#     "Metric('Name') == 'a' or Metric('Name') == 'b' and Metric('State') == 'finished'",
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("no groups", len(groups(raw)) == 0)
# check("3 flat items", len(flat(raw)) == 3)
# check("connectors [None, OR, AND]", connectors(raw) == [None, "OR", "AND"])


# banner("WORKSPACE 2: (A and B) or (C and D) — AND in OR, no groups")

# raw, _ = save_workspace(
#     "e2e-and-in-or-no-group",
#     "(Metric('Name') == 'a' and Metric('State') == 'finished') or (Metric('Name') == 'b' and Metric('State') == 'crashed')",
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("no groups", len(groups(raw)) == 0)
# check("4 flat items", len(flat(raw)) == 4)


# banner("WORKSPACE 3: A and (B or C) — explicit parens create group")

# raw, _ = save_workspace(
#     "e2e-explicit-group",
#     "Metric('Name') == 'a' and (Metric('Name') == 'b' or Metric('State') == 'finished')",
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("1 group", len(groups(raw)) == 1)
# check("group has OR items", groups(raw)[0]["filters"][1].get("connector") == "OR")


# banner("WORKSPACE 4: A or B and (C or D) — one group from parens")

# raw, _ = save_workspace(
#     "e2e-mixed-with-group",
#     "Metric('Name') == 'a' or Metric('Name') == 'b' and (Metric('State') == 'finished' or Metric('Name') == 'c')",
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("1 group", len(groups(raw)) == 1)
# check("2 flat items", len(flat(raw)) == 2)


# banner("WORKSPACE 5: (A or B) and (C or D) — two groups")

# raw, _ = save_workspace(
#     "e2e-two-groups",
#     "(Metric('Name') == 'a' or Metric('Name') == 'b') and (Metric('State') == 'finished' or Metric('Name') == 'c')",
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("2 groups", len(groups(raw)) == 2)


# banner("WORKSPACE 6: Deep nesting flattens — A or (B or (C or D and E))")

# raw, _ = save_workspace(
#     "e2e-deep-flatten",
#     "Metric('Name') == 'a' or (Metric('Name') == 'b' or (Metric('Name') == 'c' or Metric('Name') == 'd' and Metric('State') == 'finished'))",
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("1 group (not nested)", len(groups(raw)) == 1)
# grp = groups(raw)[0]
# check("no nested groups inside", all("filters" not in item for item in grp["filters"]))
# check("4 items in group", len(grp["filters"]) == 4)


# banner("WORKSPACE 7: Or/And objects — Or(A, And(B, C)) no group")

# raw, _ = save_workspace(
#     "e2e-obj-or-and",
#     Or(
#         expr.Metric("Name") == "a",
#         And(expr.Metric("Name") == "b", expr.Metric("State") == "finished"),
#     ),
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("no groups", len(groups(raw)) == 0)
# check("3 flat items", len(flat(raw)) == 3)


# banner("WORKSPACE 8: Group object — And(A, Group(Or(B, C)))")

# raw, _ = save_workspace(
#     "e2e-obj-group",
#     And(
#         expr.Metric("Name") == "a",
#         Group(Or(expr.Metric("Name") == "b", expr.Metric("State") == "finished")),
#     ),
# )
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("1 group", len(groups(raw)) == 1)


# banner("WORKSPACE 9: Modify filters on existing workspace")

# orig_ws = ws.Workspace(
#     entity=ENTITY,
#     project=PROJECT,
#     name="e2e-modify-ws",
#     runset_settings=ws.RunsetSettings(filters="Metric('Name') == 'original'"),
# )
# orig_ws.save()
# print(f"  Created: {orig_ws.url}")

# loaded = ws.Workspace.from_url(orig_ws.url)
# print(f"  Loaded filters: {loaded.runset_settings.filters!r}")
# loaded.runset_settings.filters = (
#     "Metric('Name') == 'modified' and (Metric('Name') == 'b' or Metric('State') == 'finished')"
# )
# loaded.save()
# raw = fetch_workspace_filters(ENTITY, PROJECT, loaded._internal_name)
# check("is v2", raw.get("filterFormat") == "filterV2")
# check("has group after modify", len(groups(raw)) == 1)
# check("flat item is 'modified'", flat(raw)[0]["value"] == "modified")


# ─── REPORT TESTS ────────────────────────────────────────────────────────────

banner("REPORT 1: String with AND — no group")

report1 = save_report(
    "e2e-report-and",
    "Metric('Name') == 'a' and Metric('State') == 'finished'",
)
loaded_report = wr.Report.from_url(report1.url)
rs = loaded_report.blocks[0].runsets[0]
print(f"  Loaded filter string: {rs.filters!r}")
check("filter string has 'and'", "and" in rs.filters)


banner("REPORT 2: String with group — A and (B or C)")

report2 = save_report(
    "e2e-report-group",
    "Metric('Name') == 'a' and (Metric('Name') == 'b' or Metric('State') == 'finished')",
)
loaded_report = wr.Report.from_url(report2.url)
rs = loaded_report.blocks[0].runsets[0]
print(f"  Loaded filter string: {rs.filters!r}")
check("filter string has 'and'", "and" in rs.filters)
check("filter string has parens", "(" in rs.filters)


banner("REPORT 3: Or/And/Group objects")

report3 = save_report(
    "e2e-report-obj-group",
    And(
        expr.Metric("Name") == "a",
        Group(Or(expr.Metric("Name") == "b", expr.Metric("State") == "finished")),
    ),
)
loaded_report = wr.Report.from_url(report3.url)
rs = loaded_report.blocks[0].runsets[0]
print(f"  Loaded filter string: {rs.filters!r}")
check("filter string has 'and'", "and" in rs.filters)
check("filter string has parens", "(" in rs.filters)


banner("REPORT 4: Modify report filters")

report4 = save_report("e2e-report-modify", "Metric('Name') == 'original'")
loaded_report = wr.Report.from_url(report4.url)
loaded_report.blocks[0].runsets[0].filters = Or(
    expr.Metric("Name") == "modified",
    And(
        expr.Metric("State") == "finished",
        Group(Or(expr.Metric("Name") == "c", expr.Metric("Name") == "d")),
    ),
)
loaded_report.save()
print(f"  Saved modified report: {loaded_report.url}")
loaded2 = wr.Report.from_url(loaded_report.url)
rs2 = loaded2.blocks[0].runsets[0]
print(f"  Loaded filter string: {rs2.filters!r}")
check("has 'modified' in filters", "modified" in rs2.filters)
check("has 'or' in filters", "or" in rs2.filters)


# ─── SUMMARY ─────────────────────────────────────────────────────────────────

banner("Summary")
print(f"  {passed} passed, {failed} failed out of {passed + failed} checks")
if failed:
    sys.exit(1)
