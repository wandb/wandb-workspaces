import wandb_workspaces.reports.v2 as wr
import os
from dotenv import load_dotenv

load_dotenv()
WANDB_API_KEY = os.getenv("WANDB_API_KEY")


report = wr.Report.from_url(
    "https://wandb.ai/luis_team_test/reports_api_run_color/reports/Untitled-Report--VmlldzoxMTc2ODM3OA=="
    )
print(report)