import os

import wandb_workspaces.workspaces as ws

# A Workspace is a single saved view; from_url() returns it directly. To copy a
# view to another project, load it, point it at the destination, and save it as
# a new view.

# !! edit to your source entity, project, and saved view !!
source_entity = os.getenv("WANDB_ENTITY")
source_project = os.getenv("WANDB_PROJECT")
saved_view = "your-view-id"

# !! edit to your destination entity, project, and view name !!
target_entity = "target-entity"
target_project = "target-project"
target_view_name = "Copied view"

# 1. Load the source view. Its sections, panels, and settings are all populated.
url = f"https://wandb.ai/{source_entity}/{source_project}?nw={saved_view}"
workspace = ws.Workspace.from_url(url)

# 2. Point it at the destination and name the copy.
workspace.entity = target_entity
workspace.project = target_project
workspace.name = target_view_name

# 3. Save as a new view in the destination project; logs the new view's URL.
workspace.save_as_new_view()

# NOTE: an auto-generated view regenerates its panels from the target project's
# metrics; an explicitly-built view carries its panels as-is, so those may render
# empty for metrics the target project hasn't logged. In either case, your UI
# customizations - custom panels and the sections they sit in - carry over to the
# copy. Editing a customized panel's config via the SDK isn't fully supported yet,
# so the saved customization takes precedence over the edit and the SDK logs a
# warning.
