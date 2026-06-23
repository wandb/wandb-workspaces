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

import base64
import copy
import dataclasses
import os
from typing import Any, Dict, Iterable, Literal, Optional, Tuple, Union, cast
from typing import List as LList
from urllib.parse import parse_qs, urlparse, urlunparse

import wandb
from annotated_types import Annotated, Ge
from pydantic import AfterValidator, ConfigDict, Field, PositiveInt, model_validator
from pydantic.dataclasses import dataclass

from wandb_workspaces._graphql import get_app_url
from wandb_workspaces.reports.v2.interface import PanelTypes, _lookup_panel
from wandb_workspaces.reports.v2.internal import TooltipNumberOfRuns, _generate_name
from wandb_workspaces.utils.validators import validate_no_emoji, validate_url

from .. import expr
from . import internal
from ._run_color_groups import (
    RUN_COLOR_GROUP_KEY_PREFIX,
    GroupPath,
    build_run_color_group_key,
    group_path_key_from_segments,
    parse_run_color_group_key,
)


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


def _decode_run_gid_parts(value: Optional[str]):
    """Inverse of `_encode_run_gid` returning the `(slug, project, entity)`
    triple, or `None` if `value` isn't a v1 Run GID.

    Mirrors `_decode_run_gid` but exposes all three parts so the read path
    in `_from_model` can decide whether a pin is same-project (decode back
    to a bare slug, for back-compat) or cross-project (decode to a `RunRef`).
    """
    if not value:
        return None
    try:
        decoded = base64.b64decode(value, validate=True).decode("utf-8")
    except Exception:
        return None
    parts = decoded.split(":")
    if len(parts) >= 5 and parts[0] in ("Run", "BucketType") and parts[1] == "v1":
        slug = ":".join(parts[2:-2])
        project = parts[-2]
        entity = parts[-1]
        return (slug, project, entity)
    return None


__all__ = [
    "SectionLayoutSettings",
    "SectionPanelSettings",
    "Section",
    "WorkspaceSettings",
    "RunSettings",
    "RunsetSettings",
    "RunRef",
    "GroupPath",
    "Workspace",
]

dataclass_config = ConfigDict(validate_assignment=True, extra="forbid")


def _key_to_string(key: expr.Key) -> str:
    return f"{key.section}:{key.name}"


def _groupby_to_key(group: expr.MetricType) -> expr.Key:
    key = group.to_key()
    group_str = key.name if key.section == "run" else f"{key.section}.{key.name}"
    return expr.groupby_str_to_key(group_str)


def _groupby_from_key(key: expr.Key) -> expr.MetricType:
    if key.section == "config":
        path = ".".join(part for part in key.name.split(".") if part != "value")
        config = expr.Config(path)
        if _groupby_to_key(config) == key:
            return config
    return expr.BaseMetric.from_key(key)


def _group_color_path_segments(path: object) -> Optional[Tuple[Any, ...]]:
    if isinstance(path, str):
        return (path,)
    if isinstance(path, GroupPath):
        return path.segments
    return None


def _serialize_group_colors(
    group_colors: Dict[object, object],
    groupby: LList[expr.MetricType],
    runset_id: str,
) -> Dict[str, str]:
    if not group_colors:
        return {}

    if len(groupby) == 0:
        wandb.termwarn("Omitting group_colors because runset_settings.groupby is empty.")
        return {}

    group_keys = [_key_to_string(_groupby_to_key(group)) for group in groupby]
    serialized: Dict[str, str] = {}
    seen_paths: set[Tuple[str, ...]] = set()

    for raw_path, raw_color in group_colors.items():
        segments = _group_color_path_segments(raw_path)
        if segments is None:
            wandb.termwarn(
                f"Omitting group color for unsupported path key {raw_path!r}; "
                "use a string or ws.GroupPath(...)."
            )
            continue
        if len(segments) == 0:
            wandb.termwarn("Omitting group color for empty GroupPath().")
            continue
        if not all(isinstance(segment, str) for segment in segments):
            wandb.termwarn(
                f"Omitting group color for path {raw_path!r}; "
                "all group path segments must be strings."
            )
            continue
        if len(segments) > len(group_keys):
            wandb.termwarn(
                f"Omitting group color for path {raw_path!r}; depth "
                f"{len(segments)} exceeds groupby depth {len(group_keys)}."
            )
            continue
        if not isinstance(raw_color, str):
            wandb.termwarn(
                f"Omitting group color for path {raw_path!r}; color must be a string."
            )
            continue

        normalized_segments = tuple(segments)
        if normalized_segments in seen_paths:
            wandb.termwarn(
                f"Omitting duplicate group color for path {raw_path!r}; "
                "the first color for this path was kept."
            )
            continue

        seen_paths.add(normalized_segments)
        path_entries = [
            {"kind": "group", "key": group_keys[index], "value": segment}
            for index, segment in enumerate(normalized_segments)
        ]
        serialized[build_run_color_group_key(runset_id, path_entries)] = raw_color

    return serialized


def _deserialize_group_color(
    key: str,
    color: object,
    runset_id: str,
    groupby: LList[expr.Key],
) -> Optional[Tuple[object, str]]:
    parsed = parse_run_color_group_key(key)
    if parsed is None:
        return None
    if parsed["runset_id"] != runset_id:
        return None
    if not isinstance(color, str):
        return None

    path = parsed["path"]
    if len(path) == 0 or len(path) > len(groupby):
        return None

    group_keys = [_key_to_string(group) for group in groupby]
    segments = []
    for index, entry in enumerate(path):
        if entry["key"] != group_keys[index]:
            return None
        value = entry["value"]
        if not isinstance(value, str):
            return None
        segments.append(value)

    return group_path_key_from_segments(tuple(segments)), color


# RunRef is a pure data container with no validation requirements, so we use
# the stdlib `dataclasses.dataclass` (frozen) rather than `pydantic.dataclasses`.
# Pydantic v2 supports stdlib dataclasses transparently as field types, and
# this avoids a benign-but-noisy pydantic warning that fires when a frozen
# pydantic dataclass appears inside a Union[...] field annotation.
@dataclasses.dataclass(frozen=True)
class RunRef:
    """Typed reference to a W&B run, optionally in another (entity, project).

    Use for cross-project pinned and baseline runs, where a bare slug can't
    disambiguate which project the run lives in. When `entity` or `project`
    are `None`, they fall back to the enclosing workspace's own values at
    serialization time.

    Attributes:
        slug (str): The run's slug (the value of `wandb.Run.id`, also the
            last path segment of a run URL). For example, `"abc1234"`.
        entity (Optional[str]): The owning entity of the referenced run.
            `None` means "same as the workspace's entity".
        project (Optional[str]): The project the referenced run lives in.
            `None` means "same as the workspace's project".

    Example:
        ```python
        # Cross-project, fully specified
        ws.RunRef("abc1234", entity="other-team", project="other-project")

        # Same project (entity / project default to the workspace's own)
        ws.RunRef("abc1234")
        ```
    """

    slug: str
    entity: Optional[str] = None
    project: Optional[str] = None


def _resolve_run_ref(
    value: Union[str, RunRef],
    workspace_entity: str,
    workspace_project: str,
):
    """Normalize a user-supplied run reference to `(slug, entity, project)`.

    Accepted input forms:
    - `RunRef(slug, entity=None, project=None)` — `None` fields fall back
      to the workspace's own `(entity, project)`.
    - `"entity/project/slug"` slash-form string — split into 3 non-empty
      parts; anything else raises `ValueError`.
    - bare slug `"abc1234"` — paired with the workspace's own
      `(entity, project)`.

    Pre-encoded `Run:v1:` GID strings pass through unchanged; the wire
    encoder detects them and short-circuits to avoid double-encoding.
    """
    if isinstance(value, RunRef):
        return (
            value.slug,
            value.entity if value.entity is not None else workspace_entity,
            value.project if value.project is not None else workspace_project,
        )
    if not isinstance(value, str):
        raise TypeError(
            f"Run reference must be str or RunRef, got {type(value).__name__}"
        )
    # Pre-encoded GID: `_encode_run_gid` will detect and passthrough,
    # so we don't need to parse the embedded entity/project here.
    if _decode_run_gid(value) != value:
        return (value, workspace_entity, workspace_project)
    if "/" in value:
        parts = value.split("/")
        if len(parts) != 3 or not all(parts):
            raise ValueError(
                f"Cross-project run reference {value!r} must be of the form "
                "'entity/project/slug' with three non-empty parts."
            )
        entity, project, slug = parts
        return (slug, entity, project)
    return (value, workspace_entity, workspace_project)


def _encode_pin(
    value: Union[str, RunRef], workspace_entity: str, workspace_project: str
) -> str:
    """Encode a single user-supplied pin into the wire-format GID."""
    slug, entity, project = _resolve_run_ref(value, workspace_entity, workspace_project)
    return _encode_run_gid(slug, project, entity)


def _format_decoded_pin(
    value: Optional[str],
    workspace_entity: str,
    workspace_project: str,
):
    """Convert a wire-format GID into the user-facing pin shape.

    Returns:
    - The bare slug string when the decoded `(entity, project)` matches
      the workspace's own — preserving zero back-compat break for the
      same-project case.
    - A `RunRef(slug, entity, project)` when the pin lives in a different
      `(entity, project)`.
    - `value` unchanged if it isn't a v1 Run GID (forgiving for legacy or
      non-encoded values that may exist in older specs).
    """
    parts = _decode_run_gid_parts(value)
    if parts is None:
        return value
    slug, project, entity = parts
    if entity == workspace_entity and project == workspace_project:
        return slug
    return RunRef(slug=slug, entity=entity, project=project)


def _canonicalize_pin(value):
    """Canonical `(slug, entity_or_None, project_or_None)` for the
    baseline-dedupe check in `RunsetSettings.ensure_baseline_pinned`.

    Bare-slug strings canonicalize with `None` for entity/project because
    the workspace's defaults aren't visible at validator time. That's fine
    because two bare-slug entries are still equal iff their slugs are
    equal, which is the only thing the dedupe needs to detect.
    """
    if isinstance(value, RunRef):
        return (value.slug, value.entity, value.project)
    if isinstance(value, str):
        parts = _decode_run_gid_parts(value)
        if parts is not None:
            slug, project, entity = parts
            return (slug, entity, project)
        if "/" in value:
            split = value.split("/")
            if len(split) == 3 and all(split):
                entity, project, slug = split
                return (slug, entity, project)
    return (value, None, None)


def _is_internal(k):
    return k.startswith("_")


def _should_show(v):
    """This is a workaround because BaseMetric.__eq__ returns FilterExpr."""
    if isinstance(v, Iterable) and not isinstance(v, str):
        return any(_should_show(x) for x in v)
    if isinstance(v, expr.BaseMetric):
        return True
    return False


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

    @classmethod
    def _from_model(cls, model: internal.FlowConfig):
        return cls(
            columns=model.columns_per_page,
            rows=model.rows_per_page,
        )

    def _to_model(self):
        return internal.FlowConfig(
            snap_to_columns=True,
            columns_per_page=self.columns,
            rows_per_page=self.rows,
        )


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

    @classmethod
    def _from_model(cls, model: internal.LocalPanelSettings):
        x_axis = expr._convert_be_to_fe_metric_name(model.x_axis)

        return cls(
            x_axis=x_axis,
            x_min=model.x_axis_min,
            x_max=model.x_axis_max,
            smoothing_type=model.smoothing_type,
            smoothing_weight=model.smoothing_weight,
        )

    def _to_model(self):
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

    @classmethod
    def _from_model(cls, model: internal.PanelBankConfigSectionsItem):
        return cls(
            name=model.name,
            panels=[_lookup_panel(p) for p in model.panels],
            is_open=model.is_open,
            pinned=model.pinned if model.pinned is not None else False,
            layout_settings=SectionLayoutSettings._from_model(model.flow_config),
            panel_settings=SectionPanelSettings._from_model(model.local_panel_settings),
        )

    def _to_model(self):
        panel_models = [p._to_model() for p in self.panels]
        flow_config = self.layout_settings._to_model()
        local_panel_settings = self.panel_settings._to_model()

        # Add warning that panel layout only works if they set section settings layout = "custom"

        return internal.PanelBankConfigSectionsItem(
            name=self.name,
            panels=panel_models,
            is_open=self.is_open,
            pinned=self.pinned,
            flow_config=flow_config,
            local_panel_settings=local_panel_settings,
        )


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
        group_colors (Dict[Union[str, GroupPath], str]): Colors for grouped run
            hierarchy nodes. Keys follow `groupby` order; a string targets the
            first group level and `GroupPath(...)` targets nested levels.
        pinned_columns (LList[str]): List of column names to pin.
            Column names use format: "run:displayName", "summary:metric", "config:param".
            run:displayName is automatically added if not present.
            Example: ["summary:accuracy", "summary:loss"]
        baseline_run (Optional[Union[str, RunRef]]): The baseline run used
            for delta columns and comparison styling. Accepts any of:

            - a bare slug `"1mbku38n"` (the value of `wandb.Run.id`, also
              the last path segment of a run URL), interpreted as a run in
              the workspace's own project.
            - a slash-form string `"entity/project/abc1234"` for a run in
              a different entity/project (cross-project).
            - a `RunRef(slug, entity=None, project=None)`; `None`
              entity/project default to the workspace's own.

            When set, the baseline run is automatically added to
            `pinned_runs` to match the W&B app's behavior.
        pinned_runs (LList[Union[str, RunRef]]): Ordered list of runs to
            keep visible in the run selector and always fetched for plots.
            Each entry accepts the same three forms as `baseline_run`. The
            W&B app caps this list at 20 entries.

    Example:
        ```python
        # Using string filters
        RunsetSettings(
            filters="Config('learning_rate') = 0.001 and State = 'finished'",
            pinned_columns=["summary:accuracy", "summary:loss"],
            baseline_run="1mbku38n",  # wandb.Run.id (the slug from the URL)
            pinned_runs=["1mbku38n", "2u1g3j1c"],
        )

        # Cross-project pins / baseline
        RunsetSettings(
            baseline_run=RunRef(
                "abc1234", entity="other-team", project="other-project"
            ),
            pinned_runs=[
                "1mbku38n",                                  # same project
                "other-team/other-project/abc1234",          # slash shorthand
                RunRef("xyz9876", entity="t", project="p"),  # typed RunRef
            ],
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
    group_colors: Dict[object, object] = Field(default_factory=dict)
    """
    A dictionary of group path colors. A string key targets the first groupby
    level; use GroupPath(...) for nested group paths.

    Example usage:
    ```
    group_colors = {
        "sweep_alpha": "#4E79A7",
        GroupPath("sweep_alpha", "model_vit"): "#59A14F",
    }
    ```
    """

    # Column management
    pinned_columns: LList[str] = Field(default_factory=list)

    # Baseline / pinned runs
    baseline_run: Optional[Union[str, RunRef]] = None
    pinned_runs: LList[Union[str, RunRef]] = Field(default_factory=list)

    # Internal fields for backend serialization (not user-facing)
    _visible_columns: LList[str] = Field(default_factory=list, init=False, repr=False)
    _column_order: LList[str] = Field(default_factory=list, init=False, repr=False)
    _custom_run_colors_passthrough: Dict[str, object] = Field(
        default_factory=dict, init=False, repr=False
    )

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

        The dedupe check compares canonical `(slug, entity, project)`
        tuples (see `_canonicalize_pin`), so a baseline given as
        `RunRef("abc", "e", "p")` is correctly recognized as already
        present when `pinned_runs` contains the slash-form `"e/p/abc"`.
        """
        if self.baseline_run is not None:
            baseline_canon = _canonicalize_pin(self.baseline_run)
            pinned_canons = {_canonicalize_pin(p) for p in self.pinned_runs}
            if baseline_canon not in pinned_canons:
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
        group_colors: Dict[object, object] = {}
        custom_run_colors_passthrough: Dict[str, object] = {}
        runset_model = model.spec.section.run_sets[0]

        disabled_runs = runset_model.selections.tree
        for item in disabled_runs:
            if isinstance(item, str):
                run_settings[item] = RunSettings(disabled=True)
            else:
                for child_id in item.children:
                    run_settings[child_id] = RunSettings(disabled=True)

        custom_run_colors = model.spec.section.custom_run_colors
        for k, v in custom_run_colors.items():
            if k == "ref":
                continue

            if isinstance(k, str) and k.startswith(RUN_COLOR_GROUP_KEY_PREFIX):
                group_color = _deserialize_group_color(
                    k, v, runset_model.id, runset_model.grouping
                )
                if group_color is None:
                    custom_run_colors_passthrough[k] = v
                else:
                    path_key, color = group_color
                    if path_key not in group_colors:
                        group_colors[path_key] = color
                continue

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
        )

        # Extract column settings from run_feed
        run_feed = model.spec.section.run_sets[0].run_feed
        # Only extract pinned_columns - visible_columns and column_order are derived from it
        pinned_columns = [
            col for col, is_pinned in run_feed.column_pinned.items() if is_pinned
        ]

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
                groupby=[_groupby_from_key(v) for v in runset_model.grouping],
                order=[expr.Ordering.from_key(s) for s in runset_model.sort.keys],
                run_settings=run_settings,
                group_colors=group_colors,
                pinned_columns=pinned_columns,
                baseline_run=_format_decoded_pin(
                    runset_model.baseline_run_id,
                    model.entity,
                    model.project,
                ),
                pinned_runs=[
                    _format_decoded_pin(rid, model.entity, model.project)
                    for rid in (runset_model.pinned_run_ids or [])
                ],
            ),
        )
        obj.runset_settings._custom_run_colors_passthrough = (
            custom_run_colors_passthrough
        )
        obj._internal_name = model.name
        obj._internal_id = model.id
        obj._internal_runset_id = runset_model.id
        obj._stashed_filters_v2 = stashed_v2
        obj._stashed_filter_string = filter_string
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
        point_viz_method = (
            "bucketing-gorilla"
            if self.settings.point_visualization_method == "bucketing"
            else "sampling"
        )
        suppress_legends = (
            None if not self.settings.remove_legends_from_panels else True
        )
        color_run_names = None if self.settings.tooltip_color_run_names else False
        internal_settings = internal.ViewspecSectionSettings(
            x_axis=x_axis,
            x_axis_min=self.settings.x_min,
            x_axis_max=self.settings.x_max,
            smoothing_type=self.settings.smoothing_type,
            smoothing_weight=self.settings.smoothing_weight,
            ignore_outliers=self.settings.ignore_outliers,
            suppress_legends=suppress_legends,
            tooltip_number_of_runs=self.settings.tooltip_number_of_runs,
            color_run_names=color_run_names,
            max_runs=self.settings.max_runs,
            point_visualization_method=point_viz_method,
            should_auto_generate_panels=self.auto_generate_panels,
        )

        # Convert list format (SDK) to dict format (backend) for columns
        # column_visible and column_pinned are the same (pinned columns are the only visible ones. We pass this for consistency but other columns will be visibile in the FE)
        column_pinned_dict = {col: True for col in self.runset_settings.pinned_columns}
        column_visible_dict = column_pinned_dict  # Same as pinned

        # Use internal _column_order if set, otherwise use pinned_columns as order
        column_order = (
            self.runset_settings._column_order
            if self.runset_settings._column_order
            else list(self.runset_settings.pinned_columns)
        )

        if (
            self._stashed_filters_v2 is not None
            and self.runset_settings.filters == self._stashed_filter_string
        ):
            filters_value = self._stashed_filters_v2
        else:
            filters_value = expr.filters_tree_to_v2(
                expr.expr_to_filters(self.runset_settings.filters)  # type: ignore[arg-type] # validator ensures this is always str
            )

        runset_id = self._internal_runset_id
        if self.runset_settings.group_colors and not runset_id:
            runset_id = _generate_name()
            object.__setattr__(self, "_internal_runset_id", runset_id)

        custom_run_colors = {
            **self.runset_settings._custom_run_colors_passthrough,
            **_serialize_group_colors(
                self.runset_settings.group_colors,
                self.runset_settings.groupby,
                runset_id,
            ),
            **{
                id: config.color
                for id, config in self.runset_settings.run_settings.items()
            },
        }

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
                        settings=internal.PanelBankConfigSettings(
                            sort_alphabetically=self.settings.sort_panels_alphabetically,
                            auto_organize_prefix=auto_organize_prefix,
                        ),
                        sections=sections,
                    ),
                    panel_bank_section_config=internal.PanelBankSectionConfig(
                        pinned=False
                    ),
                    settings=internal_settings,
                    run_sets=[
                        internal.Runset(
                            id=runset_id,
                            run_feed=internal.RunFeed(
                                column_pinned=column_pinned_dict,
                                column_visible=column_visible_dict,
                                column_order=column_order,
                                column_widths={},  # No column widths support
                            ),
                            search=internal.RunsetSearch(
                                query=self.runset_settings.query,
                                is_regex=is_regex,
                            ),
                            filters=filters_value,
                            grouping=[
                                _groupby_to_key(g)
                                for g in self.runset_settings.groupby
                            ],
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
                            baseline_run_id=(
                                _encode_pin(
                                    self.runset_settings.baseline_run,
                                    self.entity,
                                    self.project,
                                )
                                if self.runset_settings.baseline_run
                                else None
                            ),
                            pinned_run_ids=(
                                [
                                    _encode_pin(s, self.entity, self.project)
                                    for s in self.runset_settings.pinned_runs
                                ]
                                if self.runset_settings.pinned_runs
                                else None
                            ),
                        ),
                    ],
                    custom_run_colors=custom_run_colors,
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
