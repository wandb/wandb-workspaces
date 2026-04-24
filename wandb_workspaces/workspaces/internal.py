import json
from typing import Any, Dict, Optional
from typing import List as LList

import wandb
from annotated_types import Annotated, Ge
from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel
from wandb_gql import gql

# these internal objects should be factored out into a separate module as a
# shared dependency between Workspaces and Reports API
from wandb_workspaces.reports.v2.internal import *  # noqa: F403
from wandb_workspaces.reports.v2.internal import (
    PanelBankConfig,
    PanelBankSectionConfig,
    PointVizMethod,
    Runset,
    SmoothingType,
    TooltipNumberOfRuns,
)
from wandb_workspaces.utils.validators import validate_spec_version

CLIENT_SPEC_VERSION = -1
SPEC_VERSION_KEY = "version"


class WorkspaceAPIBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class ViewspecSectionSettings(WorkspaceAPIBaseModel):
    smoothing_weight: Annotated[int, Ge(0)] = 0
    smoothing_type: SmoothingType = "exponential"
    x_axis: str = "_step"
    ignore_outliers: bool = False
    use_runs_table_grouping_in_panels: bool = True
    x_axis_min: Optional[float] = None
    x_axis_max: Optional[float] = None
    color_run_names: Optional[bool] = None
    max_runs: Optional[int] = None
    point_visualization_method: Optional[PointVizMethod] = None
    suppress_legends: Optional[bool] = None
    tooltip_number_of_runs: Optional[TooltipNumberOfRuns] = None
    should_auto_generate_panels: bool = False

    @computed_field  # type: ignore[misc]
    @property
    def smoothing_active(self) -> bool:
        return self.smoothing_type != "none" or self.smoothing_weight != 0

    @computed_field  # type: ignore[misc]
    @property
    def x_axis_active(self) -> bool:
        return (
            self.x_axis != "_step"
            or self.x_axis_min is not None
            or self.x_axis_max is not None
        )


class ViewspecSection(WorkspaceAPIBaseModel):
    panel_bank_config: PanelBankConfig
    panel_bank_section_config: PanelBankSectionConfig

    # this is intentionally dict because it has arbitrary keys (the run ids)
    custom_run_colors: dict

    name: str = ""
    run_sets: LList[Runset] = Field(default_factory=lambda: [Runset()])
    settings: ViewspecSectionSettings = Field(default_factory=ViewspecSectionSettings)
    open_run_set: int = 0
    open_viz: bool = True


# unfortunate nomenclature... this is actually a workspace's view's spec...
class WorkspaceViewspec(WorkspaceAPIBaseModel):
    section: ViewspecSection
    viz_expanded: bool = False
    library_expanded: bool = True


class View(WorkspaceAPIBaseModel):
    entity: str
    project: str
    display_name: str
    name: str
    id: str
    spec: WorkspaceViewspec

    @classmethod
    def from_name(cls, entity: str, project: str, view_name: str) -> "View":
        # NOTE: There is a naming inconsistency in how views are stored where
        # view names are sometimes `nw-{id}-v`, and sometimes just `id`.
        # This is an unfortunate but necessary workaround...
        view_query_view_name = _internal_name_to_url_query_str(view_name)

        view_dict = get_view_dict(entity, project, view_query_view_name)

        spec = view_dict["spec"]
        display_name = view_dict["displayName"]
        id = view_dict["id"]
        parsed_spec = WorkspaceViewspec.model_validate_json(spec)

        return cls(
            entity=entity,
            project=project,
            display_name=display_name,
            name=view_name,
            id=id,
            spec=parsed_spec,
        )


def upsert_view2(view: View) -> Dict[str, Any]:
    query = gql(
        """
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
    )

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

    response = api.client.execute(query, variables)

    return response


def get_view_dict(entity: str, project: str, view_name: str) -> Dict[str, Any]:
    # Use this query because it let you use view_name instead of id
    query = gql(
        """
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
    )

    api = wandb.Api()

    response = api.client.execute(
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


def _internal_name_to_url_query_str(name: str) -> str:
    name = name.replace("nw-", "").replace("-v", "")
    return name


def _url_query_str_to_internal_name(name: str) -> str:
    return f"nw-{name}-v"


def _generate_view_name() -> str:
    random_id = wandb.util.generate_id(11)
    name = _url_query_str_to_internal_name(random_id)
    return name
