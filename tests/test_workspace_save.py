"""Saving a workspace: conflict checks, and the fallback for older servers."""

from unittest.mock import patch

import pytest

import wandb_workspaces.workspaces as ws
import wandb_workspaces.workspaces._api as ws_api

from wandb_workspaces.workspaces._api import VIEW_SPEC_CONFLICT_MESSAGE

from .fake_view_server import (
    UPDATED_AT_EDITED_ELSEWHERE,
    UPDATED_AT_LOADED,
    UPDATED_AT_SAVED,
    UPDATED_AT_SAVED_AGAIN,
    UNKNOWN_FIELD_MESSAGE,
    FakeViewServer,
    capture_termwarns,
    load_workspace,
    sends_last_updated_at,
    view_spec_conflict_error,
)


def test_load_workspace_reads_updated_at():
    server = FakeViewServer()
    workspace = load_workspace(server)

    [(query, _)] = server.queries("query View")
    assert "updatedAt" in query
    assert workspace._internal_updated_at == UPDATED_AT_LOADED


def test_save_loaded_workspace_sends_the_updated_at_it_read():
    server = FakeViewServer()
    workspace = load_workspace(server)

    with patch("wandb.Api", return_value=server.api):
        workspace.save()

    [(query, variables)] = server.upserts()
    assert "$lastUpdatedAt: DateTime" in query
    assert "lastUpdatedAt: $lastUpdatedAt" in query
    # Sent exactly as read: the server compares the timestamps for equality.
    assert variables["lastUpdatedAt"] == UPDATED_AT_LOADED
    assert variables["id"] == "view-id"


def test_consecutive_saves_send_the_updated_at_from_the_previous_save():
    server = FakeViewServer()
    workspace = load_workspace(server)

    # Each save moves the view's updated_at on, so the second save only
    # succeeds if it sends the timestamp the first one returned.
    with patch("wandb.Api", return_value=server.api):
        workspace.save()
        workspace.save()

    first, second = server.upserts()
    assert first[1]["lastUpdatedAt"] == UPDATED_AT_LOADED
    assert second[1]["lastUpdatedAt"] == UPDATED_AT_SAVED
    assert workspace._internal_updated_at == UPDATED_AT_SAVED_AGAIN


def test_save_new_workspace_is_not_guarded():
    server = FakeViewServer()

    with patch("wandb.Api", return_value=server.api):
        workspace = ws.Workspace(entity="ent", project="proj")
        workspace.save()

    [upsert] = server.upserts()
    assert not sends_last_updated_at(upsert)
    # The timestamp from the create guards the next save.
    assert workspace._internal_updated_at == UPDATED_AT_SAVED


def test_save_as_new_view_is_not_guarded():
    server = FakeViewServer()
    workspace = load_workspace(server)

    with patch("wandb.Api", return_value=server.api):
        workspace.save_as_new_view()

    [upsert] = server.upserts()
    assert not sends_last_updated_at(upsert)
    assert "id" not in upsert[1]
    assert workspace._internal_updated_at == UPDATED_AT_SAVED


def test_save_raises_conflict_error_when_view_changed_since_load():
    server = FakeViewServer()
    workspace = load_workspace(server)
    server.edit_elsewhere()

    with patch("wandb.Api", return_value=server.api):
        with pytest.raises(
            ws.ViewSpecConflictError, match="changed since it was loaded"
        ) as e:
            workspace.save()

    assert VIEW_SPEC_CONFLICT_MESSAGE in str(e.value.__cause__)
    # A conflict is never retried without the check.
    assert len(server.upserts()) == 1
    # A refused save leaves the workspace, and the view, as they were.
    assert workspace._internal_updated_at == UPDATED_AT_LOADED
    assert server.updated_at == UPDATED_AT_EDITED_ELSEWHERE


def test_save_raises_conflict_error_when_view_changed_between_saves():
    server = FakeViewServer()
    workspace = load_workspace(server)

    with patch("wandb.Api", return_value=server.api):
        workspace.save()
        server.edit_elsewhere()
        with pytest.raises(ws.ViewSpecConflictError):
            workspace.save()

    assert server.updated_at == UPDATED_AT_EDITED_ELSEWHERE


@pytest.mark.parametrize(
    "error",
    [
        Exception("VIEW_SPEC_CONFLICT: workspace changed since you loaded it"),
        Exception("Workspace changed since you loaded it"),
    ],
)
def test_conflict_detected_from_error_text(error):
    assert ws_api._is_view_spec_conflict(error)


def test_other_save_errors_are_raised_without_retry():
    error = RuntimeError("permission denied")
    server = FakeViewServer(upsert_error=error)
    workspace = load_workspace(server)

    with patch("wandb.Api", return_value=server.api):
        with pytest.raises(RuntimeError) as e:
            workspace.save()

    assert e.value is error
    assert len(server.upserts()) == 1


def test_save_retries_without_check_when_server_lacks_field(monkeypatch):
    warnings = capture_termwarns(monkeypatch)
    server = FakeViewServer(unknown_field_message=UNKNOWN_FIELD_MESSAGE)
    workspace = load_workspace(server)
    # Without the check, an edit made elsewhere is overwritten, as before 0.84.
    server.edit_elsewhere()

    with patch("wandb.Api", return_value=server.api):
        workspace.save()
        workspace.save()

    # Each save tries the check first and retries once without it. Nothing is
    # remembered between saves, so up-to-date servers never pay for a retry.
    assert [sends_last_updated_at(u) for u in server.upserts()] == [
        True,
        False,
        True,
        False,
    ]
    assert workspace._internal_updated_at == UPDATED_AT_SAVED_AGAIN
    assert len([w for w in warnings if "does not support conflict checks" in w]) == 2


@pytest.mark.parametrize(
    "error",
    [
        view_spec_conflict_error(),
        Exception('In field "description": Unknown field.'),
        Exception("Unknown field"),
    ],
    ids=["conflict", "other-field", "no-field-name"],
)
def test_unknown_last_updated_at_field_not_matched_by_other_errors(error):
    assert not ws_api._is_unknown_last_updated_at_field(error)


def test_save_existing_view_without_updated_at_is_refused():
    # A server that returns a view without updatedAt, e.g. an old row whose
    # updated_at is NULL: the next save can't be checked, so it is refused.
    server = FakeViewServer(saved_updated_ats=())

    with patch("wandb.Api", return_value=server.api):
        workspace = ws.Workspace(entity="ent", project="proj")
        workspace.save()
        with pytest.raises(ValueError, match="last update time is unknown"):
            workspace.save()

    # Only the create was sent, so nothing on the server can be overwritten.
    assert len(server.upserts()) == 1
