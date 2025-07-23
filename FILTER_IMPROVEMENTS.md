# W&B Reports Filter Improvements

## Overview

We've significantly improved the filtering functionality for W&B Reports to make it more intuitive and user-friendly. The new `FilterBuilder` API eliminates the need to figure out complex filter strings and provides a type-safe interface that matches what users see in the W&B UI.

## The Problem

Previously, users had to write complex filter strings like:
```python
runset = Runset(project=project, entity=entity, filters='Metric(\'displayName\') in [\'test_run6\']')
```

This was problematic because:
- Users had to know that "Name" in the UI corresponds to `displayName` internally
- The syntax was complex and error-prone
- No IDE autocomplete support
- Difficult to discover the correct field names

## The Solution

The new `FilterBuilder` API provides intuitive methods that match UI terminology:

```python
from wandb_workspaces.reports.v2 import FilterBuilder

# Filter by run name
runset = Runset(
    entity=entity,
    project=project,
    filters=[FilterBuilder.name("test_run6")]
)
```

## Key Features

### 1. UI-Friendly Field Names
The API uses the same names you see in the W&B UI:
- `name()` instead of `Metric('displayName')`
- `state()` instead of `Metric('state')`
- `tags()` instead of `Metric('tags')`

### 2. Type-Safe with Autocomplete
Full IDE support with type hints and autocomplete.

### 3. Consistent API
The same `FilterBuilder` works for both Reports and Workspaces:

```python
# Reports
runset = wr.Runset(filters=[FilterBuilder.name("my_run")])

# Workspaces
workspace = Workspace(
    runset_settings=RunsetSettings(
        filters=[FilterBuilder.name("my_run")]
    )
)
```

## Filter Examples

### Basic Filters

```python
# Filter by run name
FilterBuilder.name("test_run")
FilterBuilder.name(["run1", "run2", "run3"])  # Multiple names

# Filter by run state
FilterBuilder.state("finished")
FilterBuilder.state(["finished", "running"])

# Filter by tags
FilterBuilder.tags(["important", "baseline"])

# Filter by user
FilterBuilder.user("alice")

# Filter by run ID
FilterBuilder.id("abc123")
```

### Config Filters

```python
# Exact match
FilterBuilder.config("learning_rate", 0.001)

# Comparisons
FilterBuilder.config("epochs", 50, ">")
FilterBuilder.config("batch_size", 32, ">=")

# Check if config exists
FilterBuilder.config("model.layers")

# Multiple values
FilterBuilder.config("model.type", ["cnn", "rnn"], "in")
```

### Summary Metric Filters

```python
# Compare summary metrics
FilterBuilder.summary("loss", 0.5, "<")
FilterBuilder.summary("accuracy", 0.9, ">=")

# Check if metric exists
FilterBuilder.summary("custom_metric")
```

### Time-based Filters

```python
# Filter by creation time
FilterBuilder.created_after("2024-01-01T00:00:00Z")
FilterBuilder.created_before("2024-12-31T23:59:59Z")

# Filter by duration
FilterBuilder.duration(3600, ">")  # Runs longer than 1 hour
```

### Combining Filters

```python
# AND multiple filters together
filters = FilterBuilder.combine(
    FilterBuilder.name(["run1", "run2"]),
    FilterBuilder.config("epochs", 50, ">"),
    FilterBuilder.summary("accuracy", 0.8, ">="),
    operator="and"  # Currently only "and" is supported
)

runset = wr.Runset(filters=filters)
```

## Complete Example

```python
import wandb_workspaces.reports.v2 as wr
from wandb_workspaces.reports.v2 import FilterBuilder

# Create a report with multiple filtered runsets
report = wr.Report(
    entity="my-team",
    project="my-project",
    title="ML Experiment Results",
    description="Comparing different model configurations"
)

panel_grid = wr.PanelGrid(
    runsets=[
        # Recent successful runs
        wr.Runset(
            name="Recent Runs",
            entity="my-team",
            project="my-project",
            filters=[
                FilterBuilder.state("finished"),
                FilterBuilder.created_after("2024-01-01")
            ]
        ),
        # High-performing models
        wr.Runset(
            name="Best Models",
            entity="my-team", 
            project="my-project",
            filters=FilterBuilder.combine(
                FilterBuilder.summary("accuracy", 0.95, ">="),
                FilterBuilder.summary("loss", 0.1, "<"),
                FilterBuilder.config("model.type", "transformer")
            )
        ),
        # Specific experiment
        wr.Runset(
            name="Experiment A",
            entity="my-team",
            project="my-project", 
            filters=[
                FilterBuilder.tags(["experiment-a", "v2"]),
                FilterBuilder.config("learning_rate", 0.001, ">")
            ]
        )
    ],
    panels=[
        wr.LinePlot(x="Step", y=["loss", "accuracy"]),
        wr.ScatterPlot(x=wr.Summary("epoch"), y=wr.Summary("val_accuracy"))
    ]
)

report.blocks = [panel_grid]
report.save()
```

## Migration Guide

### Old Way
```python
# Complex string expressions
filters = "Metric('displayName') in ['run1', 'run2']"
filters = "Config('learning_rate').value > 0.001"
filters = "Summary('loss').value < 0.5 and Metric('state') == 'finished'"
```

### New Way
```python
# Simple, intuitive methods
filters = [FilterBuilder.name(["run1", "run2"])]
filters = [FilterBuilder.config("learning_rate", 0.001, ">")]
filters = [
    FilterBuilder.summary("loss", 0.5, "<"),
    FilterBuilder.state("finished")
]
```

## Backward Compatibility

The old string-based filter syntax is still supported for backward compatibility:
```python
# This still works
runset = wr.Runset(filters="Metric('displayName') in ['test_run']")

# But the new way is recommended
runset = wr.Runset(filters=[FilterBuilder.name("test_run")])
```

## Benefits

1. **Intuitive**: Method names match what you see in the UI
2. **Discoverable**: IDE autocomplete helps you find the right method
3. **Type-safe**: Catch errors at development time
4. **Consistent**: Same API for Reports and Workspaces
5. **Maintainable**: Easier to read and modify

## Future Enhancements

- Support for OR operations between filter groups
- More complex operators (regex matching, etc.)
- Custom filter functions
- Filter templates for common use cases