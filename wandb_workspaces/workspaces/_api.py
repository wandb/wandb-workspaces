import json
from typing import Any, Dict

import wandb

from wandb_workspaces._graphql import execute_graphql, get_app_url
from wandb_workspaces.utils.validators import validate_spec_version

from ._view_names import (
    _internal_name_to_url_query_str,
    _url_query_str_to_internal_name,
)
from .internal import CLIENT_SPEC_VERSION, View, WorkspaceViewspec


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
    )


def upsert_view2(view: View) -> Dict[str, Any]:
    query = """
        mutation UpsertView2($id: ID, $entityName: String, $projectName: String, $type: String, $name: String, $displayName: String, $description: String, $spec: String) {
        upsertView(
            input: {id: $id, entityName: $entityName, projectName: $projectName, name: $name, displayName: $displayName, description: $description, type: $type, spec: $spec, createdUsing: WANDB_SDK}
        ) {
            view {
                id
                name
            }
            inserted
        }
        }
        """

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

    # If updating an existing view: `id` exists, so add it to variables
    if view.id:
        variables["id"] = view.id

    response = execute_graphql(api, query, variables)

    return response


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
