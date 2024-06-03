import os
from typing import Dict, Iterable, Literal, Optional
from typing import List as LList
from urllib.parse import parse_qs, urlparse, urlunparse

import wandb
from annotated_types import Annotated, Ge
from pydantic import AfterValidator, ConfigDict, Field, PositiveInt
from pydantic.dataclasses import dataclass

from wandb_workspaces.reports.v2.interface import PanelTypes, _lookup_panel
from wandb_workspaces.reports.v2.internal import TooltipNumberOfRuns
from wandb_workspaces.utils.validators import validate_no_emoji, validate_url

from .. import expr
from . import internal

__all__ = [
    "SectionLayoutSettings",
    "SectionPanelSettings",
    "Section",
    "WorkspaceSettings",
    "RunSettings",
    "RunsetSettings",
    "Workspace",
]

dataclass_config = ConfigDict(validate_assignment=True, extra="forbid")


def is_internal(k):
    return k.startswith("_")


def should_show(v):
    """This is a workaround because BaseMetric.__eq__ returns FilterExpr."""
    if isinstance(v, Iterable) and not isinstance(v, str):
        return any(should_show(x) for x in v)
    if isinstance(v, expr.BaseMetric):
        return True
    return False


@dataclass(config=dataclass_config, repr=False)
class Base:
    def __repr__(self):
        fields = (
            f"{k}={v!r}"
            for k, v in self.__dict__.items()
            if (not is_internal(k)) or (should_show(v))
        )
        fields_str = ", ".join(fields)
        return f"{self.__class__.__name__}({fields_str})"

    def __rich_repr__(self):
        for k, v in self.__dict__.items():
            if (not is_internal(k)) or (should_show(v)):
                yield k, v

    @property
    def _model(self):
        return self.to_model()

    @property
    def _spec(self):
        return self._model.model_dump(by_alias=True, exclude_none=True)


@dataclass(config=dataclass_config, repr=False)
class SectionLayoutSettings(Base):
    """Panel layout settings for a section, typically seen at the top right of the section in the UI."""

    layout: Literal["standard", "custom"] = "standard"
    """
    The layout of panels in the section
        - `standard`: Follows the default grid layout
        - `custom`: Allows per per-panel layouts controlled by the individual panel settings
    """

    columns: int = 3
    "In a standard layout, the number of columns in the layout."

    rows: int = 2
    "In a standard layout, the number of rows in the layout."

    @classmethod
    def from_model(cls, model: internal.FlowConfig):
        return cls(
            layout="standard" if model.snap_to_columns else "custom",
            columns=model.columns_per_page,
            rows=model.rows_per_page,
        )

    def to_model(self):
        return internal.FlowConfig(
            snap_to_columns=self.layout == "standard",
            columns_per_page=self.columns,
            rows_per_page=self.rows,
        )


@dataclass
class SectionPanelSettings(Base):
    """Panel settings for a section, similar to WorkspaceSettings for a section.

    Settings applied here can be overrided by more granular Panel settings in this priority:
    Section < Panel
    """

    # Axis settings
    x_axis: str = "Step"
    "X-axis metric name setting."

    x_min: Optional[float] = None
    "Minimum value for the x-axis."

    x_max: Optional[float] = None
    "Maximum value for the x-axis."

    # Smoothing settings
    smoothing_type: internal.SmoothingType = "none"
    "Smoothing type applied to all panels."

    smoothing_weight: Annotated[int, Ge(0)] = 0
    "Smoothing weight applied to all panels."

    @classmethod
    def from_model(cls, model: internal.LocalPanelSettings):
        x_axis = expr._convert_be_to_fe_metric_name(model.x_axis)

        return cls(
            x_axis=x_axis,
            x_min=model.x_axis_min,
            x_max=model.x_axis_max,
            smoothing_type=model.smoothing_type,
            smoothing_weight=model.smoothing_weight,
        )

    def to_model(self):
        x_axis = expr._convert_fe_to_be_metric_name(self.x_axis)

        return internal.LocalPanelSettings(
            x_axis=x_axis,
            x_axis_min=self.x_min,
            x_axis_max=self.x_max,
            smoothing_type=self.smoothing_type,
            smoothing_weight=self.smoothing_weight,
        )


@dataclass(config=dataclass_config, repr=False)
class Section(Base):
    """Represents a section in a workspace."""

    name: str
    "The name/title of the section."

    panels: LList[PanelTypes] = Field(default_factory=list)
    "An ordered list of panels in the section.  By default, first is top-left and last is bottom-right."

    is_open: bool = False
    "Whether the section is open or closed.  Default is closed."

    layout_settings: SectionLayoutSettings = Field(
        default_factory=SectionLayoutSettings
    )
    "Settings for panel layout in the section."

    panel_settings: SectionPanelSettings = Field(default_factory=SectionPanelSettings)
    "Panel-level settings applied to all panels in the section, similar to WorkspaceSettings for this Section."

    @classmethod
    def from_model(cls, model: internal.PanelBankConfigSectionsItem):
        return cls(
            name=model.name,
            panels=[_lookup_panel(p) for p in model.panels],
            is_open=model.is_open,
            layout_settings=SectionLayoutSettings.from_model(model.flow_config),
            panel_settings=SectionPanelSettings.from_model(model.local_panel_settings),
        )

    def to_model(self):
        panel_models = [p.to_model() for p in self.panels]
        flow_config = self.layout_settings.to_model()
        local_panel_settings = self.panel_settings.to_model()

        # Add warning that panel layout only works if they set section settings layout = "custom"

        return internal.PanelBankConfigSectionsItem(
            name=self.name,
            panels=panel_models,
            is_open=self.is_open,
            flow_config=flow_config,
            local_panel_settings=local_panel_settings,
        )


@dataclass(config=dataclass_config, repr=False)
class WorkspaceSettings(Base):
    """Settings for the workspace, typically seen at the top of the workspace in the UI.

    This object includes settings for the x-axis, smoothing, outliers, panels, tooltips, runs, and panel query bar.

    Settings applied here can be overrided by more granular Section and Panel settings in this priority:
    Workspace < Section < Panel
    """

    # Axis settings
    x_axis: str = "Step"
    "X-axis metric name setting."

    x_min: Optional[float] = None
    "Minimum value for the x-axis."

    x_max: Optional[float] = None
    "Maximum value for the x-axis."

    # Smoothing settings
    smoothing_type: internal.SmoothingType = "none"
    "Smoothing type applied to all panels."

    smoothing_weight: Annotated[int, Ge(0)] = 0
    "Smoothing weight applied to all panels."

    # Outlier settings
    ignore_outliers: bool = False
    "Ignore outliers in all panels."

    # Panel settings
    remove_legends_from_panels: bool = False
    "Remove legends from all panels."

    # Tooltip settings
    tooltip_number_of_runs: TooltipNumberOfRuns = "default"
    "The number of runs to show when hovering over a point."

    tooltip_color_run_names: bool = True
    "Whether to color run names in the tooltip to match the runset (True) or not (False)."

    # Run settings
    max_runs: PositiveInt = 10
    "The maximum number of runs to show per panel (this will be the first 10 runs in the runset)."

    point_visualization_method: Literal["bucketing", "downsampling"] = "bucketing"
    """
    Bucketing buckets all data points along the x-axis, showing the min, max, and avg within each bucket,
    which ensures that outliers and spikes are clearly displayed.

    Downsampling shows a non-deterministic selection of points which is faster to render, but may miss outliers.
    """

    # Panel query bar settings
    panel_search_query: str = ""
    "The query for the panel search bar (can be a regex expr)."

    auto_expand_panel_search_results: bool = False
    "Whether to auto-expand the panel search results."

    # Internal only
    _panel_search_history: Optional[LList[Dict[Literal["query"], str]]] = Field(
        None, init=False, repr=False
    )
    "Search history for the panel search bar."

    @classmethod
    def from_model(cls, model: internal.ViewspecSectionSettings):
        x_axis = expr._convert_be_to_fe_metric_name(model.x_axis)

        # TODO: There can be better mapping here between sane API names and the internal names
        point_viz_method: Literal["bucketing", "downsampling"]
        if (pvm := model.point_visualization_method) == "bucketing-gorilla":
            point_viz_method = "bucketing"
        elif pvm == "sampling":
            point_viz_method = "downsampling"
        elif pvm is None:
            point_viz_method = "bucketing"
        else:
            raise Exception(f"Unexpected value for {pvm=}")
        remove_legends_from_panels = False if model.suppress_legends is None else True
        tooltip_number_of_runs = (
            "default"
            if model.tooltip_number_of_runs is None
            else model.tooltip_number_of_runs
        )
        tooltip_color_run_names = True if model.color_run_names is None else False
        max_runs = 10 if model.max_runs is None else model.max_runs

        return cls(
            x_axis=x_axis,
            x_min=model.x_axis_min,
            x_max=model.x_axis_max,
            smoothing_type=model.smoothing_type,
            smoothing_weight=model.smoothing_weight,
            ignore_outliers=model.ignore_outliers,
            remove_legends_from_panels=remove_legends_from_panels,
            tooltip_number_of_runs=tooltip_number_of_runs,
            tooltip_color_run_names=tooltip_color_run_names,
            max_runs=max_runs,
            point_visualization_method=point_viz_method,
        )

    def to_model(self):
        x_axis = expr._convert_fe_to_be_metric_name(self.x_axis)
        point_viz_method = (
            "bucketing-gorilla"
            if self.point_visualization_method == "bucketing"
            else "sampling"
        )
        suppress_legends = None if not self.remove_legends_from_panels else True
        color_run_names = None if self.tooltip_color_run_names else False

        return internal.ViewspecSectionSettings(
            x_axis=x_axis,
            x_axis_min=self.x_min,
            x_axis_max=self.x_max,
            smoothing_type=self.smoothing_type,
            smoothing_weight=self.smoothing_weight,
            ignore_outliers=self.ignore_outliers,
            suppress_legends=suppress_legends,
            tooltip_number_of_runs=self.tooltip_number_of_runs,
            color_run_names=color_run_names,
            max_runs=self.max_runs,
            point_visualization_method=point_viz_method,
        )


@dataclass(config=dataclass_config, repr=False)
class RunSettings(Base):
    """Settings for a run in a runset (left hand bar)."""

    color: str = ""  # hex, css color, or rgb
    "The color of the run in the UI.  Can be hex (#ff0000), css color (red), or rgb (rgb(255, 0, 0))"

    disabled: bool = False
    "Whether the run is disabled (eye closed in the UI)."


@dataclass(config=dataclass_config, repr=False)
class RunsetSettings(Base):
    """Settings for the runset (the left bar containing runs) in a workspace."""

    query: str = ""
    "A query to filter the runset (can be a regex expr, see next param)."

    regex_query: bool = False
    "Controls whether the query (above) is a regex expr."

    filters: LList[expr.FilterExpr] = Field(default_factory=list)
    """
    A list of filters to apply to the runset.  Filters are AND'd together.
    See FilterExpr for more information on creating filters.
    """

    groupby: LList[expr.MetricType] = Field(default_factory=list)
    "A list of metrics to group by in the runset."

    order: LList[expr.Ordering] = Field(default_factory=list)
    "A list of metrics and ordering to apply to the runset."

    run_settings: Dict[str, RunSettings] = Field(default_factory=dict)
    """
    A dictionary of run settings, where the key is the run's ID and the value is a RunSettings object.

    Example usage:
    ```
    run_settings = {
        "1mbku38n": RunSettings(color="red"),
        "2u1g3j1c": RunSettings(disabled=True),
    }
    ```
    """


@dataclass(config=dataclass_config, repr=False)
class Workspace(Base):
    """Represents a W&B workspace, including sections, settings, and config for run sets."""

    entity: str
    "The entity this workspace will be saved to (usually user or team name)."

    project: str
    "The project this workspace will be saved to."

    name: Annotated[str, AfterValidator(validate_no_emoji)] = "Untitled view"
    "The name of the workspace."

    sections: LList[Section] = Field(default_factory=list)
    "An ordered list of sections in the workspace.  The first section is at the top of the workspace."

    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    "Settings for the workspace, typically seen at the top of the workspace in the UI."

    runset_settings: RunsetSettings = Field(default_factory=RunsetSettings)
    "Settings for the runset (the left bar containing runs) in a workspace."

    # Internal only
    _internal_name: str = Field("", init=False, repr=False)
    "The name of the workspace in the views table."

    _internal_id: str = Field("", init=False, repr=False)
    "The view ID of the workspace."

    _internal_runset_id: str = Field("", init=False, repr=False)
    "The runset ID of the workspace."

    @property
    def url(self):
        "The URL to the workspace in the W&B app."
        if self._internal_name == "":
            raise AttributeError(
                "save workspace or explicitly pass `_internal_name` to get a url"
            )

        base = urlparse(wandb.Api().client.app_url)

        scheme = base.scheme
        netloc = base.netloc
        path = os.path.join(self.entity, self.project)
        params = ""
        query = f"nw={internal._internal_name_to_url_query_str(self._internal_name)}"
        fragment = ""

        return urlunparse((scheme, netloc, path, params, query, fragment))

    @classmethod
    def from_model(cls, model: internal.View):
        # construct configs from disjoint parts of settings
        run_settings = {}

        disabled_runs = model.spec.section.run_sets[0].selections.tree
        for id in disabled_runs:
            run_settings[id] = RunSettings(disabled=True)

        custom_run_colors = model.spec.section.custom_run_colors
        for k, v in custom_run_colors.items():
            if k != "ref":
                id = k
                color = v

                if id not in run_settings:
                    run_settings[id] = RunSettings(color=color)
                else:
                    run_settings[id].color = color

        regex_query = True if model.spec.section.run_sets[0].search.is_regex else False

        # then construct the Workspace object
        obj = cls(
            entity=model.entity,
            project=model.project,
            name=model.display_name,
            sections=[
                Section.from_model(s)
                for s in model.spec.section.panel_bank_config.sections
            ],
            settings=WorkspaceSettings.from_model(model.spec.section.settings),
            runset_settings=RunsetSettings(
                query=model.spec.section.run_sets[0].search.query,
                regex_query=regex_query,
                filters=expr.filters_tree_to_filter_expr(
                    model.spec.section.run_sets[0].filters
                ),
                groupby=[
                    expr.BaseMetric.from_key(v)
                    for v in model.spec.section.run_sets[0].grouping
                ],
                order=[
                    expr.Ordering.from_key(s)
                    for s in model.spec.section.run_sets[0].sort.keys
                ],
                run_settings=run_settings,
            ),
        )
        obj._internal_name = model.name
        obj._internal_id = model.id
        obj._internal_runset_id = model.spec.section.run_sets[0].id
        return obj

    def to_model(self) -> internal.View:
        # hack: create sections to hide unnecessary panels
        base_sections = [s.to_model() for s in self.sections]

        possible_missing_sections = set(("Hidden Panels", "Charts", "System"))
        base_section_names = set(s.name for s in self.sections)
        missing_section_names = possible_missing_sections - base_section_names

        hidden_sections = [
            Section(name=name, is_open=False).to_model()
            for name in missing_section_names
        ]

        sections = base_sections + hidden_sections
        is_regex = True if self.runset_settings.regex_query else None

        return internal.View(
            entity=self.entity,
            project=self.project,
            display_name=self.name,
            name=self._internal_name,
            id=self._internal_id,
            spec=internal.WorkspaceViewspec(
                section=internal.ViewspecSection(
                    panel_bank_config=internal.PanelBankConfig(
                        state=1,  # TODO: What is this?
                        sections=sections,
                    ),
                    panel_bank_section_config=internal.PanelBankSectionConfig(
                        pinned=False
                    ),
                    settings=self.settings.to_model(),
                    run_sets=[
                        internal.Runset(
                            id=self._internal_runset_id,
                            search=internal.RunsetSearch(
                                query=self.runset_settings.query,
                                is_regex=is_regex,
                            ),
                            filters=expr.filter_expr_to_filters_tree(
                                self.runset_settings.filters
                            ),
                            grouping=[g.to_key() for g in self.runset_settings.groupby],
                            sort=internal.Sort(
                                keys=[o.to_key() for o in self.runset_settings.order]
                            ),
                            selections=internal.RunsetSelections(
                                tree=[
                                    id
                                    for id, config in self.runset_settings.run_settings.items()
                                    if config.disabled
                                ],
                            ),
                        ),
                    ],
                    custom_run_colors={
                        id: config.color
                        for id, config in self.runset_settings.run_settings.items()
                    },
                ),
            ),
        )

    @classmethod
    def from_url(cls, url: str):
        """Get a workspace from a URL."""

        validate_url(url)

        parsed_url = urlparse(url)
        qp = parse_qs(parsed_url.query)
        qp_view_name = qp.get("nw", [""])[0]
        internal_view_name = internal._url_query_str_to_internal_name(qp_view_name)

        _, entity, project = parsed_url.path.split("/")

        view = internal.View.from_name(entity, project, internal_view_name)
        return cls.from_model(view)

    def save(self):
        """Save a workspace to W&B."""
        view = self.to_model()

        # If creating a new view with `ws.Workspace(...)`
        if not view.name:
            view.name = internal._generate_view_name()

        resp = internal.upsert_view2(view)
        self._internal_name = resp["upsertView"]["view"]["name"]
        self._internal_id = resp["upsertView"]["view"]["id"]

        wandb.termlog(f"View saved: {self.url}")
        return self

    def save_as_new_view(self):
        """Save a workspace to W&B."""
        view = self.to_model()

        # Generate a new view name and ID
        view.name = internal._generate_view_name()
        view.id = ""

        resp = internal.upsert_view2(view)
        self._internal_name = resp["upsertView"]["view"]["name"]
        self._internal_id = resp["upsertView"]["view"]["id"]

        wandb.termlog(f"View saved: {self.url}")
        return self
