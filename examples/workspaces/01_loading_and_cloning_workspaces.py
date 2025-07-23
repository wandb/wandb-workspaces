import os

import wandb_workspaces.workspaces as ws

# !! edit to your entity, project, and saved view !!
entity = os.getenv("WANDB_ENTITY")
project = os.getenv("WANDB_PROJECT")
saved_view = "51cset95tvn"

# 1. Load a workspace from URL
url = f"https://wandb.ai/{entity}/{project}?nw={saved_view}"
workspace = ws.Workspace.from_url(url)

# 2a. Edit the workspace and save to the same view
workspace.name = "Updated Workspace Name"
workspace.save()

# 2b. Save the workspace to a new view
workspace.save_as_new_view()  # this will return a different URL
