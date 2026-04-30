"""Demo: v2 filter read path — before vs after.

Run on main to see connectors lost, run on feat/v2-filters-read to see them preserved.

    WANDB_API_KEY=<key> WANDB_BASE_URL=http://localhost:9001 python demo_v2_read.py
"""

import json

import wandb_workspaces.workspaces as ws
from wandb_workspaces.workspaces import internal

ENTITY = "marie-barrramsey-wb"
PROJECT = "taylor-pr22"
VIEW_NAME = "462wyf8o8ac"
V2_WORKSPACE_URL = f"http://localhost:9001/{ENTITY}/{PROJECT}?nw={VIEW_NAME}"

# Load the internal model (what Pydantic actually parses the filters into)
view = internal.View.from_name(
    ENTITY, PROJECT,
    internal._url_query_str_to_internal_name(VIEW_NAME),
)
parsed_filters = view.spec.section.run_sets[0].filters

print("Parsed filters (internal model):")
if isinstance(parsed_filters, dict):
    print(json.dumps(parsed_filters, indent=2))
else:
    print(parsed_filters.model_dump_json(indent=2))
print()

# Load via SDK
workspace = ws.Workspace.from_url(V2_WORKSPACE_URL)
print(f"Name:    {workspace.name}")
print(f"Filters: {workspace.runset_settings.filters}")
