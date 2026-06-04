"""Python library for programmatically working with W&B Workspace API.

```python
# How to import
import wandb_workspaces.workspaces as ws
import wandb_workspaces.reports.v2 as wr

# Example of creating a workspace
ws.Workspace(
    name="Example W&B Workspace",
    entity="entity", # entity that owns the workspace
    project="project", # project that the workspace is associated with
    sections=[
        ws.Section(
            name="Validation Metrics",
            panels=[
                wr.LinePlot(x="Step", y=["val_loss"]),
                wr.BarPlot(metrics=["val_accuracy"]),
                wr.ScalarChart(metric="f1_score", groupby_aggfunc="mean"),
            ],
            is_open=True,
        ),
    ],
)
workspace.save()
```
"""

import copy
import base64
import os
from typing import Dict, Iterable, Literal, Optional, Union, cast
from typing import List as LList
from urllib.parse import parse_qs, urlparse, urlunparse

import wandb
from annotated_types import Annotated, Ge
from pydantic import AfterValidator, ConfigDict, Field, PositiveInt, model_validator
from pydantic.dataclasses import dataclass

from wandb_workspaces._graphql import get_app_url
from wandb_workspaces.reports.v2.interface import PanelTypes, _lookup_panel
from wandb_workspaces.reports.v2.internal import TooltipNumberOfRuns
from wandb_workspaces.utils.validators import validate_no_emoji, validate_url

from .. import expr
from . import internal


def _encode_run_gid(slug: str, project: str, entity: str) -> str:
    """Encode a run slug into the GraphQL Relay GID form the viewspec stores.

    The W&B app's viewspec stores pinned/baseline runs as base64-encoded
    `Run:v1:<slug>:<project>:<entity>` GIDs (see `gorilla.RunID`). The SDK
    accepts the user-friendly slug (the value of `wandb.Run.id`) and encodes
    here at the serialization boundary, so users never see the GID form.

    If the input already looks like a v1 Run GID, it's passed through
    unchanged so users with pre-existing GID values aren't broken.
    """
    if _decode_run_gid(slug) != slug:
        return slug
    payload = f"Run:v1:{slug}:{project}:{entity}".encode("utf-8")
    return base64.b64encode(payload).decode("ascii")


def _decode_run_gid(value: Optional[str]) -> Optional[str]:
    """Inverse of `_encode_run_gid`: extract the slug from a v1 Run GID.

    Non-GID inputs (already-decoded slugs, garbage strings) are returned
    unchanged so the read path is forgiving across spec format transitions.
    """
    if not value:
        return value
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except Exception:
        return value
    parts = decoded.split(":")
    if len(parts) >= 5 and parts[0] in ("Run", "BucketType") and parts[1] == "v1":
        return ":".join(parts[2:-2])
    return value


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


def _is_internal(k):
    return k.startswith("_")


def _should_show(v):
    """This is a workaround because BaseMetric.__eq__ returns FilterExpr."""
    if isinstance(v, Iterable) and not isinstance(v, str):
        return any(_should_show(x) for x in v)
    if isinstance(v, expr.BaseMetric):
        return True
    return False


def _selection_disabled_map(selections: internal.RunsetSelections) -> Dict[str, bool]:
    is_disabled = selections.root != 0
    disabled = {}
    for item in selections.tree:
        if isinstance(item, str):
            disabled[item] = is_disabled
        else:
            for child_id in item.children:
                disabled[child_id] = is_disabled
    return disabled


def _current_selection_disabled_map(
    run_settings: Dict[str, "RunSettings"],
    original_disabled: Dict[str, bool],
    selections_root: int,
) -> Dict[str, bool]:
    return {
        run_id: settings.disabled
        for run_id, settings in run_settings.items()
        if
        (
            # root=1: tree contains hidden runs
            (selections_root != 0 and settings.disabled)
            # root=0: tree contains visible runs
            or (selections_root == 0 and not settings.disabled)
            # keep originally represented runs so removals/toggles are detected
            or run_id in original_disabled
        )
    }


@dataclass(config=dataclass_config, repr=False)
class Base:
    def __repr__(self):
        fields = (
            f"{k}={v!r}"
            for k, v in self.__dict__.items()
            if (not _is_internal(k)) or (_should_show(v))
        )
        fields_str = ", ".join(fields)
        return f"{self.__class__.__name__}({fields_str})"

    def __rich_repr__(self):
        for k, v in self.__dict__.items():
            if (not _is_internal(k)) or (_should_show(v)):
                yield k, v

    @property
    def _model(self):
        return self._to_model()

    @property
    def _spec(self):
        return self._model.model_dump(by_alias=True, exclude_none=True)


@dataclass(config=dataclass_config, repr=False)
class SectionLayoutSettings(Base):
    """Panel layout settings for a section, typically seen at the
    top right of the section of the W&B App Workspace UI.

    Attributes:
        columns (int): The number of columns in the layout. Default is 3.
        rows (int): The number of rows in the layout. Default is 2.
    """

    columns: int = 3
    rows: int = 2
    _flow_config_internal: Optional[internal.FlowConfig] = Field(
        default=None, init=False, repr=False
    )

    @classmethod
    def _from_model(cls, model: internal.FlowConfig):
        obj = cls(
            columns=model.columns_per_page,
            rows=model.rows_per_page,
        )
        obj._flow_config_internal = model
        return obj

    def _to_model(self):
        flow_config = (
            self._flow_config_internal.model_copy(deep=True)
            if self._flow_config_internal is not None
            else internal.FlowConfig()
        )
        flow_config.columns_per_page = self.columns
        flow_config.rows_per_page = self.rows
        if self._flow_config_internal is None:
            flow_config.snap_to_columns = True
        return flow_config


@dataclass
class SectionPanelSettings(Base):
    """
    Panel settings for a section, similar to `WorkspaceSettings` for a section.

    Settings applied here can be overrided by more granular Panel settings in this priority:
    Section < Panel.

    Attributes:
        x_axis (str): X-axis metric name setting. By default, set to "Step".
        x_min Optional[float]: Minimum value for the x-axis.
        x_max Optional[float]: Maximum value for the x-axis.
        smoothing_type (Literal['exponentialTimeWeighted', 'exponential', 'gaussian', 'average', 'none']): Smoothing
            type applied to all panels.
        smoothing_weight (int): Smoothing weight applied to all panels.
    """

    # Axis settings
    x_axis: str = "Step"
    x_min: Optional[float] = None
    x_max: Optional[float] = None

    # Smoothing settings
    smoothing_type: internal.SmoothingType = "none"
    smoothing_weight: Annotated[int, Ge(0)] = 0
    _local_panel_settings_internal: Optional[internal.LocalPanelSettings] = Field(
        default=None, init=False, repr=False
    )

    @classmethod
    def _from_model(cls, model: internal.LocalPanelSettings):
        x_axis = expr._convert_be_to_fe_metric_name(model.x_axis)

        obj = cls(
            x_axis=x_axis,
            x_min=model.x_axis_min,
            x_max=model.x_axis_max,
            smoothing_type=model.smoothing_type,
            smoothing_weight=model.smoothing_weight,
        )
        obj._local_panel_settings_internal = model
        return obj

    def _to_model(self):
        x_axis = expr._convert_fe_to_be_metric_name(self.x_axis)

        local_panel_settings = (
            self._local_panel_settings_internal.model_copy(deep=True)
            if self._local_panel_settings_internal is not None
            else internal.LocalPanelSettings()
        )
        local_panel_settings.x_axis = x_axis
        local_panel_settings.x_axis_min = self.x_min
        local_panel_settings.x_axis_max = self.x_max
        local_panel_settings.smoothing_type = self.smoothing_type
        local_panel_settings.smoothing_weight = self.smoothing_weight
        return local_panel_settings


@dataclass(config=dataclass_config, repr=False)
class Section(Base):
    """Represents a section in a workspace.

    Attributes:
        name (str): The name/title of the section.
        panels (LList[PanelTypes]): An ordered list of panels in the section. By default, first is top-left and last is bottom-right.
        is_open (bool): Whether the section is open or closed. Default is closed.
        pinned (bool): Whether the section is pinned. Pinned sections appear at the top of the workspace. Default is False.
        layout_settings (SectionLayoutSettings): Settings for panel layout in the section.
        panel_settings: Panel-level settings applied to all panels in the section, similar to `WorkspaceSettings` for a `Section`.
    """

    name: str
    panels: LList[PanelTypes] = Field(default_factory=list)
    is_open: bool = False
    pinned: bool = False

    layout_settings: SectionLayoutSettings = Field(
        default_factory=SectionLayoutSettings
    )
    panel_settings: SectionPanelSettings = Field(default_factory=SectionPanelSettings)
    _section_internal: Optional[internal.PanelBankConfigSectionsItem] = Field(
        default=None, init=False, repr=False
    )

    @classmethod
    def _from_model(cls, model: internal.PanelBankConfigSectionsItem):
        obj = cls(
            name=model.name,
            panels=[_lookup_panel(p) for p in model.panels],
            is_open=model.is_open,
            pinned=model.pinned if model.pinned is not None else False,
            layout_settings=SectionLayoutSettings._from_model(model.flow_config),
            panel_settings=SectionPanelSettings._from_model(model.local_panel_settings),
        )
        obj._section_internal = model
        return obj

    def _to_model(self):
        panel_models = [p._to_model() for p in self.panels]
        flow_config = self.layout_settings._to_model()
        local_panel_settings = self.panel_settings._to_model()

        # Add warning that panel layout only works if they set section settings layout = "custom"

        section = (
            self._section_internal.model_copy(deep=True)
            if self._section_internal is not None
            else internal.PanelBankConfigSectionsItem()
        )
        section.name = self.name
        section.panels = panel_models
        section.is_open = self.is_open
        section.pinned = self.pinned
        section.flow_config = flow_config
        section.local_panel_settings = local_panel_settings
        return section


@dataclass(config=dataclass_config, repr=False)
class WorkspaceSettings(Base):
    """Settings for the workspace, typically seen at the top of the workspace in the UI.

    This object includes settings for the x-axis, smoothing, outliers, panels, tooltips, runs, and panel query bar.

    Settings applied here can be overrided by more granular Section and Panel settings in this priority:
    Workspace < Section < Panel

    Attributes:
        x_axis (str): X-axis metric name setting.
        x_min (Optional[float]): Minimum value for the x-axis.
        x_max (Optional[float]): Maximum value for the x-axis.
        smoothing_type (Literal['exponentialTimeWeighted', 'exponential', 'gaussian', 'average', 'none']): Smoothing
            type applied to all panels.
        smoothing_weight (int): Smoothing weight applied to all panels.
        ignore_outliers (bool): Ignore outliers in all panels.
        sort_panels_alphabetically (bool): Sorts panels in all sections alphabetically.
        group_by_prefix (Literal["first", "last"]): Group panels by the first or up to last
            prefix (first or last). Default is set to `last`.
        remove_legends_from_panels (bool): Remove legends from all panels.
        tooltip_number_of_runs (Literal["default", "all", "none"]): The number of runs to show in the tooltip.
        tooltip_color_run_names (bool): Whether to color run names in the tooltip to
            match the runset (True) or not (False). Default is set to `True`.
        max_runs (int): The maximum number of runs to show per panel (this will be the first 10 runs in the runset).
        point_visualization_method (Literal["line", "point", "line_point"]): The visualization method for points.
        panel_search_query (str): The query for the panel search bar (can be a regex expression).
        auto_expand_panel_search_results (bool): Whether to auto expand the panel search results.
    """

    # Axis settings
    x_axis: str = "Step"
    x_min: Optional[float] = None
    x_max: Optional[float] = None

    # Smoothing settings
    smoothing_type: internal.SmoothingType = "none"
    smoothing_weight: Annotated[int, Ge(0)] = 0

    # Outlier settings
    ignore_outliers: bool = False

    # Section settings
    sort_panels_alphabetically: bool = False

    group_by_prefix: Literal["first", "last"] = "last"
    """
    Group panels by the first or up to last prefix
    
    first: "a/b/c/d" -> section a
    last: "a/b/c/d" -> section a/b/c
    """

    # Panel settings
    remove_legends_from_panels: bool = False

    # Tooltip settings
    tooltip_number_of_runs: TooltipNumberOfRuns = "default"
    tooltip_color_run_names: bool = True

    # Run settings
    max_runs: PositiveInt = 10
    point_visualization_method: Literal["bucketing", "downsampling"] = "bucketing"
    """
    Bucketing buckets all data points along the x-axis, showing the min, max, and avg within each bucket,
    which ensures that outliers and spikes are clearly displayed.

    Downsampling shows a non-deterministic selection of points which is faster to render, but may miss outliers.
    """

    # Panel query bar settings
    panel_search_query: str = ""
    auto_expand_panel_search_results: bool = False

    # Internal only
    _panel_search_history: Optional[LList[Dict[Literal["query"], str]]] = Field(
        None, init=False, repr=False
    )
    "Search history for the panel search bar."


@dataclass(config=dataclass_config, repr=False)
class RunSettings(Base):
    """Settings for a run in a runset (left hand bar).

    Attributes:
        color (str): The color of the run in the UI.  Can be hex (#ff0000), css color (red), or rgb (rgb(255, 0, 0))
        disabled (bool): Whether the run is deactivated (eye closed in the UI). Default is set to `False`.
    """

    color: str = ""  # hex, css color, or rgb
    disabled: bool = False


@dataclass(config=dataclass_config, repr=False)
class RunsetSettings(Base):
    """Settings for the runset (the left bar containing runs) in a workspace.

    Attributes:
        query (str): A query to filter the runset (can be a regex expr, see next param).
        regex_query (bool): Controls whether the query (above) is a regex expr. Default is set to `False`.
        filters (Union[str, LList[FilterExpr], Or, And]): Filters for the runset.
            - As a list of FilterExpr: filters are AND'd together.
            - As a string: Python-like expressions, e.g., "Config('lr') = 0.001 and State = 'finished'"
              Supports operators: =, ==, !=, <, >, <=, >=, in, not in, and, or
            - As an Or/And combinator: allows OR logic and nested groups.
              e.g., Or(And(Config("lr") == 0.01, Metric("State") == "finished"), Config("lr") == 0.1)
        groupby (LList[expr.MetricType]): A list of metrics to group by in the runset. Set to
            `Metric`, `Summary`, `Config`, `Tags`, or `KeysInfo`.
        order (LList[expr.Ordering]): A list of metrics and ordering to apply to the runset.
        run_settings (Dict[str, RunSettings]): A dictionary of run settings, where the key
            is the run's ID and the value is a RunSettings object.
        pinned_columns (LList[str]): List of column names to pin.
            Column names use format: "run:displayName", "summary:metric", "config:param".
            run:displayName is automatically added if not present.
            Example: ["summary:accuracy", "summary:loss"]
        baseline_run (Optional[str]): W&B run slug of the baseline run (the
            value of `wandb.Run.id`, e.g. `"1mbku38n"` — also the last path
            segment of a run URL). Used for delta columns and comparison
            styling. When set, the baseline run is automatically added to
            `pinned_runs` to match the W&B app's behavior. Must refer to a
            run in the workspace's own project — cross-project pins are not
            supported by this SDK yet (see the W&B app's "Add cross-project
            runs" drawer for the UI equivalent).
        pinned_runs (LList[str]): Ordered list of W&B run slugs to keep
            visible in the run selector and always fetched for plots. Pass
            slug strings (`wandb.Run.id`), not GraphQL IDs. The W&B app
            caps this at 20 entries.

    Example:
        ```python
        # Using string filters (new)
        RunsetSettings(
            filters="Config('learning_rate') = 0.001 and State = 'finished'",
            pinned_columns=["summary:accuracy", "summary:loss"],
            baseline_run="1mbku38n",  # wandb.Run.id (the slug from the URL)
            pinned_runs=["1mbku38n", "2u1g3j1c"],
        )

        # Using FilterExpr list (original way)
        RunsetSettings(
            filters=[expr.Config("learning_rate") == 0.001],
            pinned_columns=["summary:accuracy", "summary:loss"],
        )
        ```
    """

    query: str = ""
    regex_query: bool = False
    filters: Union[str, LList[expr.FilterExpr], expr.Or, expr.And] = ""
    groupby: LList[expr.MetricType] = Field(default_factory=list)
    "A list of metrics to group by in the runset."

    order: LList[expr.Ordering] = Field(
        default_factory=lambda: [
            expr.Ordering(expr.Metric("CreatedTimestamp"), ascending=False)
        ]
    )
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

    # Column management
    pinned_columns: LList[str] = Field(default_factory=list)

    # Baseline / pinned runs
    baseline_run: Optional[str] = None
    pinned_runs: LList[str] = Field(default_factory=list)

    # Internal fields for backend serialization (not user-facing)
    _visible_columns: LList[str] = Field(default_factory=list, init=False, repr=False)
    _column_order: LList[str] = Field(default_factory=list, init=False, repr=False)

    @model_validator(mode="after")
    def validate_and_setup_columns(self):
        """Ensure run:displayName is present and set up internal column fields."""
        if self.pinned_columns:
            # Ensure run:displayName is in pinned_columns
            if "run:displayName" not in self.pinned_columns:
                # Add it as the first element
                self.pinned_columns.insert(0, "run:displayName")
            elif self.pinned_columns[0] != "run:displayName":
                # Move it to the first position
                self.pinned_columns.remove("run:displayName")
                self.pinned_columns.insert(0, "run:displayName")

            # Set internal fields to match pinned_columns
            # Use object.__setattr__ to avoid recursion with Pydantic validation
            object.__setattr__(self, "_visible_columns", list(self.pinned_columns))
            object.__setattr__(self, "_column_order", list(self.pinned_columns))

        return self

    @model_validator(mode="after")
    def ensure_baseline_pinned(self):
        """Mirror the W&B app's invariant: a baseline run is always also pinned.

        The frontend's `setBaselineRun` action handler routes through
        `setRunPinnedAndBaseline`, so any spec produced by the UI has the
        baseline ID present in `pinnedRunIds`. We enforce the same here so
        SDK-produced specs match.
        """
        if self.baseline_run and self.baseline_run not in self.pinned_runs:
            new_pinned = list(self.pinned_runs)
            new_pinned.append(self.baseline_run)
            object.__setattr__(self, "pinned_runs", new_pinned)
        if len(self.pinned_runs) > 20:
            wandb.termwarn(
                f"pinned_runs has {len(self.pinned_runs)} entries; "
                "the W&B app caps pinned runs at 20."
            )
        return self

    @model_validator(mode="after")
    def convert_filterexpr_list_to_string(self):
        """Convert FilterExpr list or Or/And to string expression."""
        if isinstance(self.filters, list):
            object.__setattr__(
                self, "filters", expr.filterexpr_list_to_string(self.filters)
            )
        elif isinstance(self.filters, (expr.Or, expr.And)):
            tree = expr._filter_items_to_filters_tree([self.filters])
            v2 = expr.filters_tree_to_v2(tree)
            object.__setattr__(self, "filters", expr.filters_v2_to_string(v2))
        return self


@dataclass(config=dataclass_config, repr=False)
class Workspace(Base):
    """Represents a W&B workspace, including sections, settings, and config for run sets.

    Attributes:
        entity (str): The entity this workspace will be saved to (usually user or team name).
        project (str): The project this workspace will be saved to.
        name: The name of the workspace.
        sections (LList[Section]): An ordered list of sections in the workspace.
            The first section is at the top of the workspace.
        settings (WorkspaceSettings): Settings for the workspace, typically seen at
            the top of the workspace in the UI.
        runset_settings (RunsetSettings): Settings for the runset
            (the left bar containing runs) in a workspace.
        auto_generate_panels (bool): Whether to automatically generate panels for all keys logged in this project.
            Recommended if you would like all available data to be visualized by default.
            This can only be set during workspace creation and cannot be modified afterward.
    """

    entity: str
    project: str
    name: Annotated[str, AfterValidator(validate_no_emoji)] = "Untitled view"
    sections: LList[Section] = Field(default_factory=list)
    settings: WorkspaceSettings = Field(default_factory=WorkspaceSettings)
    runset_settings: RunsetSettings = Field(default_factory=RunsetSettings)
    _auto_generate_panels: bool = Field(
        default=False, repr=True, alias="auto_generate_panels"
    )

    # Internal only
    _internal_name: str = Field("", init=False, repr=False)
    "The name of the workspace in the views table."

    _internal_id: str = Field("", init=False, repr=False)
    "The view ID of the workspace."

    _internal_runset_id: str = Field("", init=False, repr=False)
    "The runset ID of the workspace."

    _stashed_filters_v2: Optional[dict] = Field(default=None, init=False, repr=False)
    _stashed_filter_string: Optional[str] = Field(default=None, init=False, repr=False)

    _internal_view: Optional[internal.View] = Field(None, init=False, repr=False)
    "The original loaded view, used to preserve frontend-owned viewspec fields."

    @property
    def auto_generate_panels(self) -> bool:
        return self._auto_generate_panels

    @property
    def url(self):
        "The URL to the workspace in the W&B app."
        if self._internal_name == "":
            raise AttributeError(
                "save workspace or explicitly pass `_internal_name` to get a url"
            )

        base = urlparse(get_app_url(wandb.Api()))

        scheme = base.scheme
        netloc = base.netloc
        path = os.path.join(self.entity, self.project)
        params = ""
        query = f"nw={internal._internal_name_to_url_query_str(self._internal_name)}"
        fragment = ""

        return urlunparse((scheme, netloc, path, params, query, fragment))

    @classmethod
    def _from_model(cls, model: internal.View):
        # construct configs from disjoint parts of settings
        run_settings = {}

        selections = model.spec.section.run_sets[0].selections
        disabled_runs = selections.tree
        is_disabled = selections.root != 0
        for item in disabled_runs:
            if isinstance(item, str):
                run_settings[item] = RunSettings(disabled=is_disabled)
            else:
                for child_id in item.children:
                    run_settings[child_id] = RunSettings(disabled=is_disabled)

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

        section_settings = model.spec.section.settings
        panel_bank_settings = model.spec.section.panel_bank_config.settings
        x_axis = expr._convert_be_to_fe_metric_name(section_settings.x_axis)
        point_viz_method: Literal["bucketing", "downsampling"]
        if (pvm := section_settings.point_visualization_method) == "bucketing-gorilla":
            point_viz_method = "bucketing"
        elif pvm == "sampling":
            point_viz_method = "downsampling"
        elif pvm is None:
            point_viz_method = "bucketing"
        else:
            raise Exception(f"Unexpected value for {pvm=}")
        remove_legends_from_panels = (
            False if section_settings.suppress_legends is None else True
        )
        tooltip_number_of_runs = (
            "default"
            if section_settings.tooltip_number_of_runs is None
            else section_settings.tooltip_number_of_runs
        )
        tooltip_color_run_names = (
            True if section_settings.color_run_names is None else False
        )
        max_runs = (
            10 if section_settings.max_runs is None else section_settings.max_runs
        )
        group_by_prefix: Literal["first", "last"] = (
            "last" if panel_bank_settings.auto_organize_prefix == 2 else "first"
        )

        workspace_settings = WorkspaceSettings(
            x_axis=x_axis,
            x_min=section_settings.x_axis_min,
            x_max=section_settings.x_axis_max,
            smoothing_type=section_settings.smoothing_type,
            smoothing_weight=section_settings.smoothing_weight,
            ignore_outliers=section_settings.ignore_outliers,
            remove_legends_from_panels=remove_legends_from_panels,
            tooltip_number_of_runs=tooltip_number_of_runs,
            tooltip_color_run_names=tooltip_color_run_names,
            max_runs=max_runs,
            point_visualization_method=point_viz_method,
            sort_panels_alphabetically=panel_bank_settings.sort_alphabetically,
            group_by_prefix=group_by_prefix,
            panel_search_query=panel_bank_settings.search_query or "",
            auto_expand_panel_search_results=(
                panel_bank_settings.auto_expand_search_results or False
            ),
        )
        workspace_settings._panel_search_history = panel_bank_settings.search_history

        # Extract column settings from run_feed
        run_feed = model.spec.section.run_sets[0].run_feed
        # Only extract pinned_columns - visible_columns and column_order are derived from it
        pinned_columns = [
            col for col, is_pinned in run_feed.column_pinned.items() if is_pinned
        ]

        runset_model = model.spec.section.run_sets[0]
        if isinstance(runset_model.filters, dict) and expr.is_filter_v2(
            runset_model.filters
        ):
            stashed_v2 = copy.deepcopy(runset_model.filters)
            filter_string = expr.filters_v2_to_string(runset_model.filters)
        else:
            # Legacy filters: the workspace was saved before v2 and hasn't been
            # opened in the UI yet (which does lazy conversion).  Convert the
            # legacy Filters tree to v2.
            stashed_v2 = expr.filters_tree_to_v2(
                cast(expr.Filters, runset_model.filters)
            )
            filter_string = expr.filters_v2_to_string(stashed_v2)

        # then construct the Workspace object
        should_auto_generate_panels = (
            model.spec.section.settings.should_auto_generate_panels is True
        )
        obj = cls(
            entity=model.entity,
            project=model.project,
            name=model.display_name,
            sections=[
                Section._from_model(s)
                for s in model.spec.section.panel_bank_config.sections
            ],
            settings=workspace_settings,
            runset_settings=RunsetSettings(
                query=runset_model.search.query,
                regex_query=regex_query,
                filters=filter_string,
                groupby=[expr.BaseMetric.from_key(v) for v in runset_model.grouping],
                order=[expr.Ordering.from_key(s) for s in runset_model.sort.keys],
                run_settings=run_settings,
                pinned_columns=pinned_columns,
                baseline_run=_decode_run_gid(
                    model.spec.section.run_sets[0].baseline_run_id
                ),
                pinned_runs=[
                    _decode_run_gid(rid) or rid
                    for rid in (model.spec.section.run_sets[0].pinned_run_ids or [])
                ],
            ),
            auto_generate_panels=should_auto_generate_panels,
        )
        obj._internal_name = model.name
        obj._internal_id = model.id
        obj._internal_runset_id = runset_model.id
        obj._stashed_filters_v2 = stashed_v2
        obj._stashed_filter_string = filter_string
        obj.runset_settings._visible_columns = [
            col for col, is_visible in run_feed.column_visible.items() if is_visible
        ]
        obj.runset_settings._column_order = list(run_feed.column_order)
        obj._internal_view = model
        return obj

    def _to_model(self) -> internal.View:
        sections = [s._to_model() for s in self.sections]

        is_regex = True if self.runset_settings.regex_query else None
        auto_organize_prefix = 2 if self.settings.group_by_prefix == "last" else 1

        if self.settings.sort_panels_alphabetically:
            wandb.termwarn(
                "settings.sort_panels_alphabetically=True; this may change panel order from what is currently defined in sections!"
            )

        x_axis = expr._convert_fe_to_be_metric_name(self.settings.x_axis)
        point_viz_method: Literal["bucketing-gorilla", "sampling"] = (
            "bucketing-gorilla"
            if self.settings.point_visualization_method == "bucketing"
            else "sampling"
        )
        suppress_legends = (
            None if not self.settings.remove_legends_from_panels else True
        )
        color_run_names = None if self.settings.tooltip_color_run_names else False

        # Convert list format (SDK) to dict format (backend) for columns
        # column_visible and column_pinned are the same (pinned columns are the only visible ones. We pass this for consistency but other columns will be visibile in the FE)
        column_pinned_dict = {col: True for col in self.runset_settings.pinned_columns}
        column_visible_dict = column_pinned_dict  # Same as pinned

        if (
            self._stashed_filters_v2 is not None
            and self.runset_settings.filters == self._stashed_filter_string
        ):
            filters_value = self._stashed_filters_v2
        else:
            filters_value = expr.filters_tree_to_v2(
                expr.expr_to_filters(self.runset_settings.filters)  # type: ignore[arg-type] # validator ensures this is always str
            )

        if self._internal_view is not None:
            view = self._internal_view.model_copy(deep=True)
            view.entity = self.entity
            view.project = self.project
            view.display_name = self.name
            view.name = self._internal_name
            view.id = self._internal_id
            section = view.spec.section
        else:
            view = internal.View(
                entity=self.entity,
                project=self.project,
                display_name=self.name,
                name=self._internal_name,
                id=self._internal_id,
                spec=internal.WorkspaceViewspec(
                    section=internal.ViewspecSection(
                        panel_bank_config=internal.PanelBankConfig(state=1),
                        panel_bank_section_config=internal.PanelBankSectionConfig(
                            pinned=False
                        ),
                        custom_run_colors={},
                    ),
                ),
            )
            section = view.spec.section

        panel_bank_config = section.panel_bank_config.model_copy(deep=True)
        panel_bank_settings = panel_bank_config.settings.model_copy(deep=True)
        panel_bank_settings.sort_alphabetically = (
            self.settings.sort_panels_alphabetically
        )
        panel_bank_settings.auto_organize_prefix = auto_organize_prefix
        if (
            self.settings.panel_search_query
            or panel_bank_settings.search_query is not None
        ):
            panel_bank_settings.search_query = self.settings.panel_search_query
        if (
            self.settings.auto_expand_panel_search_results
            or panel_bank_settings.auto_expand_search_results is not None
        ):
            panel_bank_settings.auto_expand_search_results = (
                self.settings.auto_expand_panel_search_results
            )
        if self.settings._panel_search_history is not None:
            panel_bank_settings.search_history = self.settings._panel_search_history
        panel_bank_config.settings = panel_bank_settings
        panel_bank_config.sections = sections
        section.panel_bank_config = panel_bank_config

        internal_settings = section.settings.model_copy(deep=True)
        internal_settings.x_axis = x_axis
        internal_settings.x_axis_min = self.settings.x_min
        internal_settings.x_axis_max = self.settings.x_max
        internal_settings.smoothing_type = self.settings.smoothing_type
        internal_settings.smoothing_weight = self.settings.smoothing_weight
        internal_settings.ignore_outliers = self.settings.ignore_outliers
        internal_settings.suppress_legends = suppress_legends
        internal_settings.tooltip_number_of_runs = self.settings.tooltip_number_of_runs
        internal_settings.color_run_names = color_run_names
        internal_settings.max_runs = self.settings.max_runs
        internal_settings.point_visualization_method = point_viz_method
        if (
            self._internal_view is None
            or self.auto_generate_panels
            or internal_settings.should_auto_generate_panels in (False, None)
        ):
            internal_settings.should_auto_generate_panels = self.auto_generate_panels
        section.settings = internal_settings

        run_sets = list(section.run_sets)
        runset = run_sets[0].model_copy(deep=True) if run_sets else internal.Runset()
        runset.id = self._internal_runset_id

        run_feed = runset.run_feed.model_copy(deep=True)
        original_pinned_columns = [
            col for col, is_pinned in run_feed.column_pinned.items() if is_pinned
        ]
        pinned_columns_changed = (
            self._internal_view is None
            or self.runset_settings.pinned_columns != original_pinned_columns
        )
        if pinned_columns_changed:
            run_feed.column_pinned = column_pinned_dict
            run_feed.column_visible = column_visible_dict
            run_feed.column_order = list(self.runset_settings.pinned_columns)
            if self._internal_view is None:
                run_feed.column_widths = {}
        runset.run_feed = run_feed

        search = runset.search.model_copy(deep=True)
        search.query = self.runset_settings.query
        search.is_regex = is_regex
        runset.search = search
        runset.filters = filters_value
        runset.grouping = [g.to_key() for g in self.runset_settings.groupby]
        runset.sort = internal.Sort(
            keys=[o.to_key() for o in self.runset_settings.order]
        )
        runset.baseline_run_id = (
            _encode_run_gid(
                self.runset_settings.baseline_run,
                self.project,
                self.entity,
            )
            if self.runset_settings.baseline_run
            else None
        )
        runset.pinned_run_ids = (
            [
                _encode_run_gid(s, self.project, self.entity)
                for s in self.runset_settings.pinned_runs
            ]
            if self.runset_settings.pinned_runs
            else None
        )

        selections = runset.selections.model_copy(deep=True)
        original_disabled = _selection_disabled_map(runset.selections)
        current_disabled = _current_selection_disabled_map(
            self.runset_settings.run_settings, original_disabled, selections.root
        )
        if self._internal_view is None or current_disabled != original_disabled:
            if selections.root == 0:
                selections.tree = [
                    id
                    for id, config in self.runset_settings.run_settings.items()
                    if not config.disabled
                ]
            else:
                selections.tree = [
                    id
                    for id, config in self.runset_settings.run_settings.items()
                    if config.disabled
                ]
        runset.selections = selections

        if run_sets:
            run_sets[0] = runset
        else:
            run_sets = [runset]
        section.run_sets = run_sets

        custom_run_colors = dict(section.custom_run_colors)
        for run_id, config in self.runset_settings.run_settings.items():
            if config.color:
                custom_run_colors[run_id] = config.color
            else:
                custom_run_colors.pop(run_id, None)
        section.custom_run_colors = custom_run_colors

        view.spec.section = section
        return view

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
        return cls._from_model(view)

    def save(self):
        """
        Save the current workspace to W&B.

        Returns:
            Workspace: The updated workspace with the saved internal name and ID.
        """
        view = self._to_model()

        # If creating a new view with `ws.Workspace(...)`
        if not view.name:
            view.name = internal._generate_view_name()

        resp = internal.upsert_view2(view)
        self._internal_name = resp["upsertView"]["view"]["name"]
        self._internal_id = resp["upsertView"]["view"]["id"]

        wandb.termlog(f"View saved: {self.url}")
        return self

    def save_as_new_view(self):
        """
        Save the current workspace as a new view to W&B.

        Returns:
            Workspace: The updated workspace with the saved internal name and ID.
        """
        view = self._to_model()

        # Generate a new view name and ID
        view.name = internal._generate_view_name()
        view.id = ""

        resp = internal.upsert_view2(view)
        self._internal_name = resp["upsertView"]["view"]["name"]
        self._internal_id = resp["upsertView"]["view"]["id"]

        wandb.termlog(f"View saved: {self.url}")
        return self
