"""Test loading a workspace with legacy filters and modifying it."""

import os
os.environ["WANDB_BASE_URL"] = "http://localhost:9001"

import wandb_workspaces.workspaces as ws

URL = "http://localhost:9001/marie-barrramsey-wb/taylor-pr23?nw=fnsyn9n7nby"

print("Loading workspace...")
workspace = ws.Workspace.from_url(URL)

print(f"\nCurrent filters: {workspace.runset_settings.filters!r}")

workspace.runset_settings.filters += " and Config('epochs') == 10"
print(f"Modified filters: {workspace.runset_settings.filters!r}")

print("\nSaving...")
workspace.save()
print("Done!")
