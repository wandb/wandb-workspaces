"""Demo: report v2 filter write path — before vs after.

On main, saving a report with v2 filters writes a broken Pydantic-coerced tree.
On feat/v2-filters-report-write:
  - Unchanged v2 filters are written back as the original v2 dict
  - Modified v2 filters are reconverted to v2 format
  - New/legacy reports write canonical OR→AND→leaves tree

Run with:
    WANDB_API_KEY=<key> WANDB_BASE_URL=http://localhost:9001 python demo_report_write.py
"""

import json

import wandb_workspaces.reports.v2 as wr
from wandb_workspaces.reports.v2 import internal as report_internal
from wandb_workspaces.reports.v2.interface import _get_api

ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr23"
REPORT_URL = f"http://localhost:9001/{ENTITY}/{PROJECT}/reports/Untitled-Report--VmlldzoxNTg"


def banner(title):
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def fetch_report_runset_filters(report_url):
    """Fetch raw runset filters from a report's backend spec."""
    from urllib.parse import urlparse
    parsed = urlparse(report_url)
    path_parts = parsed.path.strip("/").split("/")
    entity = path_parts[0]
    project = path_parts[1]

    # Load report to get its internal view
    report = wr.Report.from_url(report_url)
    # Get the raw spec via GraphQL
    api = _get_api()
    from wandb_workspaces.reports.v2.internal import gql
    query = gql("""
    query Views($entityName: String, $name: String) {
        project(name: $name, entityName: $entityName) {
            allViews(viewType: "runs") {
                edges { node { name displayName spec } }
            }
        }
    }
    """)
    response = api.client.execute(query, {"entityName": entity, "name": project})
    for e in response["project"]["allViews"]["edges"]:
        if e["node"]["displayName"] == report.title:
            spec = json.loads(e["node"]["spec"])
            # Find the first panel grid's runset filters
            for block in spec.get("blocks", []):
                if block.get("type") == "panel-grid":
                    metadata = block.get("metadata", {})
                    run_sets = metadata.get("runSets", [])
                    if run_sets:
                        return run_sets[0].get("filters")
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: Load report, inspect runset filters
# ══════════════════════════════════════════════════════════════════════════════
# banner("Test 1: Load report and inspect runset filters")

# report = wr.Report.from_url(REPORT_URL)
# print(f"Title: {report.title}")

# for i, block in enumerate(report.blocks):
#     if isinstance(block, wr.PanelGrid):
#         for j, rs in enumerate(block.runsets):
#             print(f"\nPanelGrid[{i}] Runset[{j}]:")
#             print(f"  Filters string: {rs.filters}")
#             print(f"  _raw_filters_v2: {rs._raw_filters_v2 is not None}")
#             print(f"  _filters_internal: {rs._filters_internal is not None}")
#             if rs._raw_filters_v2:
#                 print(f"  Raw v2 dict:")
#                 print(json.dumps(rs._raw_filters_v2, indent=2))
#             if rs._filters_internal:
#                 print(f"  Internal Filters tree:")
#                 print(rs._filters_internal.model_dump_json(indent=2))


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: Modify filters and save → check what gets written
# ══════════════════════════════════════════════════════════════════════════════
# banner("Test 2: Modify report runset filters and save")

# report = wr.Report.from_url(REPORT_URL)

# for block in report.blocks:
#     if isinstance(block, wr.PanelGrid):
#         rs = block.runsets[0]
#         print(f"Original: {rs.filters}")

#         rs.filters = (
#             'Metric("Name") == "august" or Metric("Name") == "betty"'
#             ' and (Metric("State") == "finished" or Metric("Name") == "cardigan")'
#         )
#         print(f"Modified: {rs.filters}")
#         break

# report.title = "Report Write Test 2"
# report.save()
# print("\nSaved!")

# backend = fetch_report_runset_filters(report.url)
# if backend:
#     print("\nBackend filters after save:")
#     print(json.dumps(backend, indent=2))
# else:
#     print("\nCould not fetch backend filters")


# # ══════════════════════════════════════════════════════════════════════════════
# # Test 3: Save unchanged → should preserve original format
# # ══════════════════════════════════════════════════════════════════════════════
# banner("Test 3: Save report unchanged → should preserve original format")

# report = wr.Report.from_url(REPORT_URL)

# for block in report.blocks:
#     if isinstance(block, wr.PanelGrid):
#         rs = block.runsets[0]
#         print(f"Filters (not modified): {rs.filters}")
#         print(f"Has raw v2: {rs._raw_filters_v2 is not None}")
#         break

# report.title = "Report Write Test 3 - Unchanged"
# report.title = "Report Write Test 3 - Unchanged"
# report.save()
# print("\nSaved!")

# backend = fetch_report_runset_filters(report.url)
# if backend:
#     print("\nBackend filters after save:")
#     print(json.dumps(backend, indent=2))
# else:
#     print("\nCould not fetch backend filters")


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: Create a NEW report with filters
# ══════════════════════════════════════════════════════════════════════════════
banner("Test 4: Create new report with filters")

new_report = wr.Report(
    entity=ENTITY,
    project=PROJECT,
    title="Report Write Test 4 - New With Filters",
    blocks=[
        wr.PanelGrid(
            runsets=[
                wr.Runset(
                    entity=ENTITY,
                    project=PROJECT,
                    filters=(
                        'Metric("Name") == "folklore" or Metric("Name") == "evermore"'
                        ' and (Metric("State") == "finished" or Metric("Name") == "exile")'
                    ),
                ),
            ],
        ),
    ],
)

rs = new_report.blocks[0].runsets[0]
print(f"Filters: {rs.filters}")
print(f"Has raw v2: {rs._raw_filters_v2 is not None}")
print(f"Has internal tree: {rs._filters_internal is not None}")

new_report.save()
print(f"\nSaved! URL: {new_report.url}")

backend = fetch_report_runset_filters(new_report.url)
if backend:
    print("\nBackend filters after save:")
    print(json.dumps(backend, indent=2))
