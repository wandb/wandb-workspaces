# Contribution Guide

This guide will help you set up your development environment for the `wandb-workspaces` project.

## Table of Contents

- [Setting up your dev environment](#setting-up-your-dev-environment)
  - [Setting up Python](#setting-up-python)
  - [Building/installing the package](#buildinginstalling-the-package)
  - [Linting the code](#linting-the-code)
  - [Authentication with W&B](#authentication-with-wb)
- [Manual testing](#manual-testing)
- [Automated testing](#automated-testing)
  - [Running tests](#running-tests)

## Setting up your dev environment

In general, we'll be following patterns from the [W&B SDK](https://github.com/wandb/wandb/blob/main/CONTRIBUTING.md#setting-up-your-development-environment)

### Setting up Python


Before you begin, make sure you have **Python 3.9 or higher** installed on your system. You can check your Python version with:

```bash
python --version
# or
python3 --version
```

Again, we'll reference the W&B SDK section for [setting up python](https://github.com/wandb/wandb/blob/main/CONTRIBUTING.md#setting-up-python). The short version is to use uv:

```shell
pip install -U  uv
```

### Building/installing the package

We recommend installing the `wandb-workspaces` package in the editable mode with either `pip` or `uv` (you'll probably get an error from `uv` to set up your virtual environment via `uv venv`):

```shell
uv pip install -e .
```

### Linting the code

Again, we'll reference the W&B SDK section for [linting the code](https://github.com/wandb/wandb/blob/main/CONTRIBUTING.md#linting-the-code). The short version is to use pre-commit:

To install `pre-commit` run the following:

```shell
uv pip install -U pre-commit
```

### Authentication with W&B

Since this library interacts with Weights & Biases, you'll need to authenticate:

```bash
uv run wandb login
```

This will prompt you to enter your W&B API key, which you can find at https://wandb.ai/authorize.

## Manual testing

To test your local changes:

1. **Ensure you're authenticated with W&B** (if you haven't already):

   ```bash
   uv run wandb login
   ```

2. **Create a test script**:

   For example, this script will create a simple workspace in the entity/project of your choice:

   ```python
   # create_workspace.py

   import wandb_workspaces.workspaces as ws
   import wandb_workspaces.reports.v2 as wr

    entity="your-entity",  # Update this value!
    project="your-project",  # Update this value!

   # NOTE: Replace "your-entity" and "your-project" with actual W&B entity and project names
   workspace = ws.Workspace(
       name="My cool workspace",
       entity=entity,  # Update this value!
       project=project,  # Update this value!
       sections=[
           ws.Section(
               name="Charts",
               panels=[wr.LinePlot(x="Step", y=["loss"])],
               is_open=True,
           )
       ]
   )

   workspace.save()

   # Alternatively, load and modify:
   view_query_param = 'nw=nmngo2hizd9' # Update this value! Found in the url of the saved view you want to modify
   workspace = ws.Workspace.from_url(f'https://wandb.ai/{entity}/{project}/?{view_query_param}'
   ```



   **💡 Tip:** You can also use or reference one of the existing example scripts in the `examples/` directory for inspiration. These scripts demonstrate common use cases and can serve as a starting point for your testing.

3. **Run your test script**:

   ```bash
   uv run python create_workspace.py
   ```

## Automated testing

When adding a new feature or fixing an issue, please also include unit tests. Tests files are located in the `tests/` directory. This project uses **pytest** for testing.

### Running tests

```bash
# Run all tests
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests for a specific file
uv run pytest tests/test_workspaces.py

# Run a specific test function
uv run pytest tests/test_workspaces.py::test_save_workspace

# Run tests with coverage report
uv run pytest --cov=wandb_workspaces --cov-report=html
```
