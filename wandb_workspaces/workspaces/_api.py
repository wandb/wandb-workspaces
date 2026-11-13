import json
from typing import Any, Dict, Optional

import wandb

from wandb_workspaces._graphql import execute_graphql, get_app_url
from wandb_workspaces.utils.validators import validate_spec_version
from wandb_workspaces.workspaces.errors import ViewSpecConflictError

from ._view_names import (
    _internal_name_to_url_query_str,
    _url_query_str_to_internal_name,
)
from .internal import CLIENT_SPEC_VERSION, View, WorkspaceViewspec

VIEW_SPEC_CONFLICT_CODE = "VIEW_SPEC_CONFLICT"
VIEW_SPEC_CONFLICT_MESSAGE = "workspace changed since you loaded it"


def app_url() -> str:
    """The base URL of the W&B app the current credentials point at."""
    return get_app_url(wandb.Api())


def fetch_view(entity: str, project: str, view_name: str) -> View:
    # NOTE: There is a naming inconsistency in how views are stored where
    # view names are sometimes `nw-{id}-v`, and sometimes just `id`.
    # This is an unfortunate but necessary workaround...
    view_query_view_name = _internal_name_to_url_query_str(view_name)

    view_dict = get_view_dict(entity, project, view_query_view_name)

    spec = view_dict["spec"]
    display_name = view_dict["displayName"]
    id = view_dict["id"]
    parsed_spec = WorkspaceViewspec.model_validate_json(spec)

    return View(
        entity=entity,
        project=project,
        display_name=display_name,
        name=view_name,
        id=id,
        spec=parsed_spec,
        updated_at=view_dict.get("updatedAt"),
    )


def _is_view_spec_conflict(error: Exception) -> bool:
    # The service transport keeps only the error message, not the code in the
    # GraphQL extensions, so match either.
    text = str(error)
    return VIEW_SPEC_CONFLICT_CODE in text or VIEW_SPEC_CONFLICT_MESSAGE in text.lower()


def _is_unknown_last_updated_at_field(error: Exception) -> bool:
    # For backward compatibility: servers before 0.84 lack `lastUpdatedAt` and
    # reject it during validation, before anything is written.
    return 'In field "lastUpdatedAt": Unknown field' in str(error)


# `%` formatting, so the GraphQL braces need no escaping.
_UPSERT_VIEW_MUTATION = """
    mutation UpsertView2($id: ID, $entityName: String, $projectName: String, $type: String, $name: String, $displayName: String, $description: String, $spec: String%(last_updated_at_var)s) {
    upsertView(
        input: {id: $id, entityName: $entityName, projectName: $projectName, name: $name, displayName: $displayName, description: $description, type: $type, spec: $spec, createdUsing: WANDB_SDK%(last_updated_at_input)s}
    ) {
        view {
            id
            name
            updatedAt
        }
        inserted
    }
    }
    """


def _execute_upsert(
    api: Any, view: View, variables: Dict[str, Any], last_updated_at: Optional[str]
) -> Dict[str, Any]:
    if last_updated_at is None:
        query = _UPSERT_VIEW_MUTATION % {
            "last_updated_at_var": "",
            "last_updated_at_input": "",
        }
    else:
        query = _UPSERT_VIEW_MUTATION % {
            "last_updated_at_var": ", $lastUpdatedAt: DateTime",
            "last_updated_at_input": ", lastUpdatedAt: $lastUpdatedAt",
        }
        variables = {**variables, "lastUpdatedAt": last_updated_at}

    try:
        return execute_graphql(api, query, variables)
    except Exception as e:
        if _is_view_spec_conflict(e):
            raise ViewSpecConflictError(
                f"Workspace `{view.display_name}` changed since it was loaded, so "
                "the save was refused to avoid overwriting those changes. Reload it "
                "with `Workspace.from_url`, reapply your edits, and save again, or "
                "use `save_as_new_view()` to keep your version as a separate view."
            ) from e
        raise


def upsert_view2(view: View) -> Dict[str, Any]:
    api = wandb.Api()
    spec_str = view.spec.model_dump_json(by_alias=True, exclude_none=True)

    # Default: assume a new view being created, so no `id` yet
    variables = {
        "entityName": view.entity,
        "projectName": view.project,
        "name": view.name,
        "displayName": view.display_name,
        "type": "project-view",
        "description": "",
        "spec": spec_str,
        "locked": False,
    }

    # Creating a new view: no `id` yet, and no timestamp to guard the save with
    if not view.id:
        return _execute_upsert(api, view, variables, last_updated_at=None)

    # Updating an existing view: `id` exists, so add it to variables
    variables["id"] = view.id

    # Loading or saving a view always returns its updatedAt, so a missing one
    # means the workspace did not come from the server. Refuse rather than
    # save without a conflict check.
    if view.updated_at is None:
        raise ValueError(
            f"Can't save workspace `{view.display_name}`: it exists on the server "
            "but its last update time is unknown, so the save can't be checked for "
            "conflicts. Load it with `Workspace.from_url` and save that, or use "
            "`save_as_new_view()`."
        )

    try:
        return _execute_upsert(api, view, variables, view.updated_at)
    except Exception as e:
        # TODO: Remove this fallback once 0.83 is out of support (2027-07-22);
        # every supported server will then accept `lastUpdatedAt` (added in 0.84).
        if not _is_unknown_last_updated_at_field(e):
            raise
    wandb.termwarn(
        "This W&B server does not support conflict checks on workspace saves. "
        "Saving without one, so this save may overwrite changes made since the "
        "workspace was loaded."
    )
    return _execute_upsert(api, view, variables, last_updated_at=None)


def get_view_dict(entity: str, project: str, view_name: str) -> Dict[str, Any]:
    # Use this query because it let you use view_name instead of id
    query = """
        query View($entityName: String, $name: String, $viewType: String = "runs", $userName: String, $viewName: String) {
            project(name: $name, entityName: $entityName) {
                allViews(viewType: $viewType, viewName: $viewName, userName: $userName) {
                    edges {
                        node {
                            id
                            displayName
                            spec
                            updatedAt
                        }
                    }
                }
            }
        }
        """

    api = wandb.Api()

    response = execute_graphql(
        api,
        query,
        {
            "viewType": "project-view",
            "entityName": entity,
            "projectName": project,
            "name": project,
            "viewName": _url_query_str_to_internal_name(view_name),
        },
    )

    p = response.get("project")
    if p is None:
        raise ValueError(
            f"Project `{entity}/{project}` not found.  Do you have access to this project?"
        )

    edges = p.get("allViews", {}).get("edges", [])

    try:
        view = edges[0]["node"]
    except IndexError:
        raise ValueError(f"Workspace `{view_name}` not found in project `{project}`")

    spec = json.loads(view["spec"])
    validate_spec_version(spec, expected_version=CLIENT_SPEC_VERSION)

    return view
