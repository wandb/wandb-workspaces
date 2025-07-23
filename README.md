<div align="center">
  <img src="https://i.imgur.com/RUtiVzH.png" width="600" /><br><br>
</div>

# wandb-workspaces

<p align='center'>
<a href="https://pypi.python.org/pypi/wandb-workspaces"><img src="https://img.shields.io/pypi/v/wandb-workspaces" /></a>
<a href="https://circleci.com/gh/wandb/wandb-workspaces"><img src="https://img.shields.io/circleci/build/github/wandb/wandb-workspaces" /></a>
<a href="https://codecov.io/gh/wandb/wandb-workspaces/graph/badge.svg?token=XGL5D4023X"><img src="https://img.shields.io/codecov/c/gh/wandb/wandb-workspaces" /></a>
</p>

`wandb-workspaces` is a Python library for programatically working with [Weights & Biases](https://wandb.ai) workspaces and reports. This feature is in **Public Preview**.

## Quickstart
<p align='center'>
<a href="https://colab.research.google.com/github/wandb/wandb-workspaces/blob/example-notebook/Workspace_tutorial.ipynb"><img src="https://colab.research.google.com/assets/colab-badge.svg" /></a>
</p>

### 1. Install

```bash
pip install wandb-workspaces
```

OR, you can install this as an extra from the wandb library:

```bash
pip install wandb[workspaces]
```

### 2. Create a workspace

```python
import wandb_workspaces.workspaces as ws

workspace = ws.Workspace(
   name="Example W&B Workspace",
   entity="your-entity",
   project="your-project",
   sections=[
      ws.Section(
            name="Validation Metrics",
            panels=[
               wr.LinePlot(x="Step", y=["val_loss"]),
               wr.BarPlot(metrics=["val_accuracy"]),
               wr.ScalarChart(metric="f1_score", groupby_aggfunc="mean"),
            ],
            is_open=True,
      ),
   ],
).save()
```

![image](https://github.com/wandb/wandb-workspaces/assets/15385696/796083f4-2aa6-432f-b585-c04abca9022f)

### 3. Create a report

```python
import wandb_workspaces.reports as wr

report = wr.Report(
    entity="your-entity",
    project="your-project",
    title="Example W&B Report",
    blocks=[
        wr.H1("This is a heading"),
        wr.P("Some amazing insightful text about your project"),
        wr.H2(
            "This heading is collapsed",
            collapsed_blocks=[wr.P("Our model is great!")],
        ),
        wr.PanelGrid(
            panels=[
                wr.LinePlot(x="Step", y=["val_loss"]),
                wr.BarPlot(metrics=["val_accuracy"]),
                wr.ScalarChart(metric="f1_score", groupby_aggfunc="mean"),
            ]
        ),
    ],
).save()
```

![image](https://github.com/wandb/wandb-workspaces/assets/15385696/25939b7c-1f2c-4df7-9936-692464e6e3fc)

### 4. Generate code from existing reports

You can reverse-engineer any W&B report to generate the Python code needed to recreate it programmatically:

```python
import wandb_workspaces.reports as wr

# Load an existing report from its URL
report = wr.Report.from_url("https://wandb.ai/your-entity/your-project/reports/Report-Name--REPORT_ID")

# Generate the Python code to recreate this report
code = report.to_code()
print(code)

# Save the generated code to a file
with open("recreated_report.py", "w") as f:
    f.write(code)
```

This feature is particularly useful for:
- Learning how to create reports programmatically by examining existing ones
- Migrating reports between projects or entities
- Version controlling report configurations
- Creating templates from existing reports

Example output:
```python
import wandb_workspaces.reports.v2 as wr

# Create report
report = wr.Report(
    project='your-project',
    entity='your-entity',
    title='Example Report',
    description='An example report with various visualizations.'
)

# Add blocks
report.blocks = [
    wr.H1(text='Performance Metrics'),
    wr.PanelGrid(
        panels=[
            wr.LinePlot(x='Step', y=['loss', 'accuracy']),
            wr.BarPlot(metrics=['final_score'], orientation='v')
        ]
    )
]

# Save the report
report.save()
```

**Note**: If the report contains unknown block types (from newer API versions), the generated code will include comments indicating these blocks couldn't be recreated.

## More examples
<p align='center'>
<a href="https://colab.research.google.com/github/wandb/wandb-workspaces/blob/example-notebook/Workspace_tutorial.ipynb"><img src="https://colab.research.google.com/assets/colab-badge.svg" /></a>
</p>

See [examples](https://github.com/wandb/wandb-workspaces/tree/main/examples) for more detailed usage.

