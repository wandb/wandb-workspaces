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

## More examples
<p align='center'>
<a href="https://colab.research.google.com/github/wandb/wandb-workspaces/blob/example-notebook/Workspace_tutorial.ipynb"><img src="https://colab.research.google.com/assets/colab-badge.svg" /></a>
</p>

See [examples](https://github.com/wandb/wandb-workspaces/tree/main/examples) for more detailed usage.

