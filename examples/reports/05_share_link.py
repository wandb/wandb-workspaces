import os

import wandb_workspaces.reports.v2 as wr

entity = os.environ["WANDB_ENTITY"]
project = os.environ["WANDB_PROJECT"]

# Create a report and enable a shareable "magic link" so anyone with the URL
# can view it, even if the project is private.

report = wr.Report(
    entity=entity,
    project=project,
    title="Shared Report Example",
    blocks=[
        wr.H1("Nightly Status Report"),
        wr.P("This report is shared via a magic link."),
        wr.PanelGrid(
            runsets=[wr.Runset(entity=entity, project=project)],
            panels=[wr.LinePlot()],
        ),
    ],
)
report.save()

# Enable the share link — returns a URL with an access token appended.
share_url = report.enable_share_link()
print(f"Share this link: {share_url}")

# Check the current share URL at any time via the property.
print(f"Current share URL: {report.share_url}")

# To disable the share link (revokes the access token):
# report.disable_share_link()
