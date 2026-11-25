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
  - [Round-trip tests against stored workspaces](#round-trip-tests-against-stored-workspaces)

## Setting up your dev environment

In general, we'll be following patterns from the [W&B SDK](https://github.com/wandb/wandb/blob/main/CONTRIBUTING.md#setting-up-your-development-environment)

### Setting up Python


Before you begin, make sure you have **Python 3.10 or higher** installed on your system. You can check your Python version with:

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

### Round-trip tests against stored workspaces

The SDK must be able to load a workspace the app saved, save it back, and lose nothing. The tests in `tests/test_workspace_round_trip.py`, `tests/test_spec_corpus.py` and `tests/test_workspace_new_content.py` check this by serving a stored spec from a fake server, loading it with `Workspace.from_url`, saving it (untouched or after an edit), and comparing the JSON the save sent with the JSON it loaded. They also check the saved spec against the view spec schema's write contract, pinned in `schema/viewspec/`.

A save starts from the spec as loaded and applies the user's edits onto it (`wandb_workspaces/workspaces/_spec_edits.py`), so a field survives whether or not the SDK models it. New content is written in the shape the app writes for hand-made content: ids on run sets and sections, settings in `workspaceSettings` and `sectionSettings`, no default panel layout. The spec is checked against the read contract on load and the write contract on save; a key the write contract rejects is sent back as loaded, with a warning, as the app does.

**Rules for `_to_model` and `_rebuilt_spec`.** The save finds the user's edits as the difference between the rebuild right after loading and the rebuild at save time, so `_rebuilt_spec` must be a pure function of the public objects' state. It may not branch on whether the workspace has been loaded or saved before, and every id it generates must be stored on the object (a section's `_id`, the run set id, `_hidden_panels_id`), or the difference shows a phantom edit. A field added to `_to_model` with a default is written for a new workspace, and for a loaded one only when the user changes it; a user setting it to the SDK's default when the stored spec lacks the key is not detected. List items need a stable `__id__` or `id` to be matched across a reorder; items without one match by equality, then by position. A setting edited on a workspace stored in the legacy shape writes the whole modern block the app would migrate to (`_modern_settings.seed_modern_blocks`), never a partial one, because the app ignores the legacy block as soon as the modern one has a key. `tests/test_workspace_save_path.py` checks that saving twice without an edit sends the same spec; keep that passing.

If a change makes a check fail that the SDK should pass, mark it `xfail(strict=True, raises=AssertionError)` with the reason, rather than loosening the check. When a later change fixes it, the test fails until its mark is removed, so each fix shows up in the diff.

**Committed specs** live in `tests/specs/`. Each one must pass the write contract itself and must not identify a customer: build it by hand, or from a workspace of your own. Run `uv run pytest tests/test_spec_corpus.py` after adding one; the first test tells you if the write contract rejects it.

**Checking a real workspace** is a read-only, in-memory operation. The report fetches the stored spec with your `wandb login` credentials for the URL's host, loads and saves it against a fake server, and prints what the save dropped, changed and added, plus any write-contract errors. Nothing is written back, and nothing is saved to disk:

```bash
uv run python -m tests.round_trip_report "https://wandb.ai/<entity>/<project>?nw=<id>"

# Several at once, listing up to 5 paths of each kind per workspace
uv run python -m tests.round_trip_report <url> <url> --paths 5
```

Hosts that prefix the path (such as `/wandb/<entity>/<project>`) and personal workspaces (stored as `nw-<id>-w`) both work. Set `WANDB_BASE_URL` to use another API host.

The report also takes spec files and directories, and `SPEC_CORPUS=<dir> uv run pytest tests/test_spec_corpus.py -m corpus` runs one loss check per spec in a directory. Both only read specs you already have; the repo has no tool for saving them, and stored workspaces can hold customer data, so don't keep them in the repo. Corpus specs are only checked for loss, not against the write contract: stored workspaces still carry legacy keys that load migrates. Without `SPEC_CORPUS` the corpus tests are deselected, so the normal `uv run pytest` run doesn't need one.
