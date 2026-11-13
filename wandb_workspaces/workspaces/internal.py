from typing import Any, Dict, Optional
from typing import List as LList

from annotated_types import Annotated, Ge
from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_camel

# Re-exported: ARIA's skill docs import `execute_graphql` from this module.
from wandb_workspaces._graphql import execute_graphql  # noqa: F401

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
    # The app treats an absent value as True and auto-generates panels; only an
    # explicit False disables that. Keep it Optional so None is omitted on save
    # (exclude_none) and an absent flag round-trips as absent, not forced False.
    should_auto_generate_panels: Optional[bool] = None

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
    # Captures the app's modern `workspaceSettings` block so _from_model can read
    # shouldAutoGeneratePanels from it. _to_model never writes it back; emitting
    # it would stop the app migrating the legacy `settings`.
    #
    # TODO: Support all modern workspace settings.
    workspace_settings: Optional[dict] = None
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
