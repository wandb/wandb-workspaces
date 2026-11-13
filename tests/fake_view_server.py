"""A fake W&B server for testing how workspaces are loaded and saved."""

from unittest.mock import Mock, patch

import wandb_workspaces.workspaces as ws
import wandb_workspaces.workspaces.interface as ws_interface

UPDATED_AT_LOADED = "2026-11-12T15:04:05Z"
UPDATED_AT_EDITED_ELSEWHERE = "2026-11-12T15:04:07Z"
UPDATED_AT_SAVED = "2026-11-12T15:04:09Z"
UPDATED_AT_SAVED_AGAIN = "2026-11-12T15:04:13Z"

# How servers before 0.84 reject `lastUpdatedAt`, from gorilla's GraphQL validation.
UNKNOWN_FIELD_MESSAGE = (
    'Argument "input" has invalid value {id: $id, lastUpdatedAt: $lastUpdatedAt}.\n'
    'In field "lastUpdatedAt": Unknown field.'
)


def service_api_error(message, http_status):
    from wandb.proto.wandb_api_pb2 import ApiErrorResponse
    from wandb.sdk.lib.service.service_connection import WandbApiFailedError

    # What the service transport raises: only the message and status survive,
    # not the code in the GraphQL extensions.
    return WandbApiFailedError(
        message,
        response=ApiErrorResponse(message=message, http_status=http_status),
    )


def view_spec_conflict_error():
    return service_api_error("workspace changed since you loaded it", 409)


class FakeViewServer:
    """Answers the workspace GraphQL calls by query, and records them.

    Like gorilla, it refuses a save whose `lastUpdatedAt` is not the view's
    current `updated_at`, and moves `updated_at` on with each save.

    `unknown_field_message`, when set, makes the server reject any upsert that
    sends `lastUpdatedAt`, like a server before 0.84. `upsert_error` is raised
    by every upsert instead of saving.
    """

    def __init__(
        self,
        *,
        unknown_field_message=None,
        saved_updated_ats=(UPDATED_AT_SAVED, UPDATED_AT_SAVED_AGAIN),
        upsert_error=None,
    ):
        self.updated_at = UPDATED_AT_LOADED
        self.unknown_field_message = unknown_field_message
        self.saved_updated_ats = list(saved_updated_ats)
        self.upsert_error = upsert_error
        self.client = Mock()
        self.client.app_url = "https://app.wandb.test"
        self.api = Mock()
        self.api._service_api = self.client
        self.client.execute_graphql.side_effect = self._execute

    def _execute(self, query, variables=None):
        if "query View" in query:
            spec = ws.Workspace(entity="ent", project="proj")._to_model().spec
            return {
                "project": {
                    "allViews": {
                        "edges": [
                            {
                                "node": {
                                    "id": "view-id",
                                    "displayName": "Loaded",
                                    "spec": spec.model_dump_json(
                                        by_alias=True, exclude_none=True
                                    ),
                                    "updatedAt": self.updated_at,
                                }
                            }
                        ]
                    }
                }
            }

        if "upsertView" in query:
            if self.unknown_field_message and "lastUpdatedAt" in query:
                raise service_api_error(self.unknown_field_message, 400)
            if self.upsert_error is not None:
                raise self.upsert_error
            last_updated_at = (variables or {}).get("lastUpdatedAt")
            if last_updated_at is not None and last_updated_at != self.updated_at:
                raise view_spec_conflict_error()
            view = {"id": "view-id", "name": "nw-saved-v"}
            if self.saved_updated_ats:
                self.updated_at = self.saved_updated_ats.pop(0)
                view["updatedAt"] = self.updated_at
            return {"upsertView": {"view": view, "inserted": False}}

        raise AssertionError(f"unexpected query: {query}")

    def edit_elsewhere(self, updated_at=UPDATED_AT_EDITED_ELSEWHERE):
        """Change the view as another writer would, such as the browser."""
        self.updated_at = updated_at

    def queries(self, marker):
        return [
            (c.args[0], c.kwargs.get("variables") or {})
            for c in self.client.execute_graphql.call_args_list
            if marker in c.args[0]
        ]

    def upserts(self):
        return self.queries("upsertView")


def load_workspace(server):
    with patch("wandb.Api", return_value=server.api):
        return ws.Workspace.from_url("https://app.wandb.test/ent/proj?nw=abc123")


def sends_last_updated_at(upsert):
    query, variables = upsert
    return "lastUpdatedAt" in query or "lastUpdatedAt" in variables


def capture_termwarns(monkeypatch):
    warnings = []
    monkeypatch.setattr(ws_interface.wandb, "termwarn", warnings.append)
    return warnings
