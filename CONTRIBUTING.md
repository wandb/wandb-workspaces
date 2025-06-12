# Contribution Guide

This guide will help you set up your development environment for the `wandb-workspaces` project.

## Table of Contents

- [Setting up your dev environment](#setting-up-your-dev-environment)
- [Manual testing](#manual-testing)
- [Automated testing](#automated-testing)

## Setting up your dev environment

Before you begin, make sure you have **Python 3.9 or higher** installed on your system. You can check your Python version with:

```bash
python --version
# or
python3 --version
```

### 1. Install Poetry

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

After installation, make sure Poetry is in your PATH by adding this to your shell profile (`.bashrc`, `.zshrc`, etc.):

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Verify the installation:

```bash
poetry --version
```

**What is Poetry?** Poetry is a Python package manager that handles dependencies, virtual environments, and packaging. It's similar to npm for Node.js or Cargo for Rust.

### 2. Install dependencies

```bash
poetry install -E test
poetry run pre-commit install
```

**What happened here?**

- `poetry install` creates a virtual environment and installs all project dependencies. `-E test` flag includes optional test dependencies
- Pre-commit hooks automatically run code quality checks before each commit

### 3. Authenticate with W&B

Since this library interacts with Weights & Biases, you'll need to authenticate:

```bash
poetry run wandb login
```

This will prompt you to enter your W&B API key, which you can find at https://wandb.ai/authorize.

### 4. (Optional) Activate the virtual environment

Poetry automatically creates an isolated virtual environment for the project. To activate it, run `poetry shell`. This allows you to omit the `poetry run` prefix when running commands.

## Manual testing

To test your local changes:

1. **Ensure you're authenticated with W&B** (if you haven't already):

   ```bash
   poetry run wandb login
   ```

2. **Create a test script**:

   For example, this script will create a simple workspace in the entity/project of your choice:

   ```python
   # create_workspace.py

   import wandb_workspaces.workspaces as ws
   import wandb_workspaces.reports.v2 as wr

   # NOTE: Replace "your-entity" and "your-project" with actual W&B entity and project names
   workspace = ws.Workspace(
       name="My cool workspace",
       entity="your-entity",  # Update this value!
       project="your-project",  # Update this value!
       sections=[
           ws.Section(
               name="Charts",
               panels=[wr.LinePlot(x="Step", y=["loss"])],
               is_open=True,
           )
       ]
   )

   workspace.save()
   ```

   **💡 Tip:** You can also use or reference one of the existing example scripts in the `examples/` directory for inspiration. These scripts demonstrate common use cases and can serve as a starting point for your testing.

3. **Run your test script**:

   ```bash
   poetry run python create_workspace.py
   ```

## Automated testing

When adding a new feature or fixing an issue, please also include unit tests. Tests files are located in the `tests/` directory. This project uses **pytest** for testing.

### Running tests

```bash
# Run all tests
poetry run pytest

# Run tests with verbose output
poetry run pytest -v

# Run tests for a specific file
poetry run pytest tests/test_workspaces.py

# Run a specific test function
poetry run pytest tests/test_workspaces.py::test_save_workspace

# Run tests with coverage report
poetry run pytest --cov=wandb_workspaces --cov-report=html
```
