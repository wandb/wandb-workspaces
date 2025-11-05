"""
Pytest configuration and fixtures for wandb-workspaces tests.

This file is automatically loaded by pytest before running tests.
"""

import pytest
from pydantic.dataclasses import rebuild_dataclass


@pytest.fixture(scope="session", autouse=True)
def rebuild_forward_refs():
    """
    Rebuild dataclasses with forward references to resolve Pydantic type issues.

    This is needed for the idempotency tests which use polyfactory to generate
    test instances. Without `from __future__ import annotations`, Pydantic needs
    forward references to be explicitly resolved after all types are defined.
    """
    # Import the modules that contain the dataclasses
    from wandb_workspaces.reports.v2 import interface as reports_interface

    # Import expr module so forward references to it can be resolved
    from wandb_workspaces import expr  # noqa: F401

    # Rebuild H1, H2, H3 which have forward refs to BlockTypes (which includes Link)
    rebuild_dataclass(reports_interface.H1, force=True, raise_errors=False)
    rebuild_dataclass(reports_interface.H2, force=True, raise_errors=False)
    rebuild_dataclass(reports_interface.H3, force=True, raise_errors=False)

    # Rebuild Runset which has forward ref to expr.FilterExpr
    rebuild_dataclass(reports_interface.Runset, force=True, raise_errors=False)

    # Rebuild PanelGrid which has forward refs to Runset and PanelTypes
    rebuild_dataclass(reports_interface.PanelGrid, force=True, raise_errors=False)

    # Return to allow test execution
    yield
