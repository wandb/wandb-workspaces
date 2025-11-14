"""This is a rewrite of the expression system currently used in Reports.

In a future version, Reports will migrate to this expression syntax.
"""

import warnings
from dataclasses import dataclass
from typing import Any, ClassVar, Dict, List, Literal, Optional, Union

from wandb_workspaces.reports.v2.internal import Filters, Key, SortKey, SortKeyKey
from wandb_workspaces.utils.invertable_dict import InvertableDict

__all__ = [
    # Core classes for creating filters and orderings
    "Config",
    "Metric",
    "Summary",
    "Tags",
    "Ordering",
    # Filter expression type (needed for type hints)
    "FilterExpr",
    # Convenience conversion utilities
    "string_to_filterexpr_list",
    "filterexpr_list_to_string",
]

Expression = Dict[str, Any]


FE_METRIC_NAME_MAP = InvertableDict(
    {
        "ID": "name",
        "Name": "displayName",
        "Tags": "tags",
        "State": "state",
        "CreatedTimestamp": "createdAt",
        "Runtime": "duration",
        "User": "username",
        "Sweep": "sweep",
        "Group": "group",
        "JobType": "jobType",
        "Hostname": "host",
        "UsingArtifact": "inputArtifacts",
        "OutputtingArtifact": "outputArtifacts",
        "Step": "_step",
        "RelativeTime(Wall)": "_absolute_runtime",
        "RelativeTime(Process)": "_runtime",
        "WallTime": "_timestamp",
    }
)


# Mapping custom operators to Python operators
OPERATOR_MAP = InvertableDict(
    {
        "AND": "and",
        "OR": "or",
        "=": "==",
        "!=": "!=",
        "<": "<",
        "<=": "<=",
        ">": ">",
        ">=": ">=",
        "IN": "in",
        "NIN": "not in",
    }
)


@dataclass(eq=False, frozen=True)
class BaseMetric:
    name: str
    section: ClassVar[str]  # declared in subclasses

    def __eq__(self, other: Any) -> "FilterExpr":  # type: ignore
        return FilterExpr.create("=", self, other)

    def __ne__(self, other: Any) -> "FilterExpr":  # type: ignore
        return FilterExpr.create("!=", self, other)

    def __lt__(self, other: Any) -> "FilterExpr":
        # Map < to <= for consistency with backend behavior
        warnings.warn(
            f"Using '<' operator with {self.__class__.__name__} is being mapped to '<=' for platform consistency. "
            "Consider using '<=' explicitly in your filters.",
            UserWarning,
            stacklevel=2,
        )
        return FilterExpr.create("<=", self, other)

    def __le__(self, other: Any) -> "FilterExpr":
        return FilterExpr.create("<=", self, other)

    def __gt__(self, other: Any) -> "FilterExpr":
        # Map > to >= for consistency with backend behavior
        warnings.warn(
            f"Using '>' operator with {self.__class__.__name__} is being mapped to '>=' for platform consistency. "
            "Consider using '>=' explicitly in your filters.",
            UserWarning,
            stacklevel=2,
        )
        return FilterExpr.create(">=", self, other)

    def __ge__(self, other: Any) -> "FilterExpr":
        return FilterExpr.create(">=", self, other)

    def isin(self, other: List[Any]) -> "FilterExpr":
        return FilterExpr.create("IN", self, other)

    def notin(self, other: List[Any]) -> "FilterExpr":
        return FilterExpr.create("NIN", self, other)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}('{self.name}')"

    def to_key(self) -> Key:
        name = _convert_fe_to_be_metric_name(self.name)
        return Key(section=self.section, name=name)

    # TODO: Key and SortKeyKey are actually the same shape, they're just named differently.
    @classmethod
    def from_key(cls, key: Union[Key, SortKeyKey]) -> "MetricType":
        section = key.section
        name = _convert_be_to_fe_metric_name(key.name)
        metric_cls = METRIC_TYPE_MAP.get(section, BaseMetric)
        return metric_cls(name)


@dataclass(eq=False, frozen=True)
class Metric(BaseMetric):
    """Typically metrics that you log with `wandb.log`.

    These also include any metrics that are logged automatically as part of the run, like `Created Timestamp`
    """

    section: ClassVar[Literal["run"]] = "run"


@dataclass(eq=False, frozen=True)
class Summary(BaseMetric):
    """Typically the last value for metrics that you log with `wandb.log`."""

    section: ClassVar[Literal["summary"]] = "summary"


@dataclass(eq=False, frozen=True)
class Config(BaseMetric):
    """Typically the values you log when setting `wandb.config`."""

    section: ClassVar[Literal["config"]] = "config"


@dataclass(eq=False, frozen=True)
class Tags(BaseMetric):
    """The values when setting `wandb.run.tags`.

    Usage: ws.Tags().isin(['tag1', 'tag2'])

    Note: Tags doesn't take a name parameter - it always refers to 'tags' in the run section.
    """

    name: str = "tags"  # Fixed name, always "tags"
    section: ClassVar[Literal["run"]] = "run"  # Tags are in the run section


@dataclass(eq=False, frozen=True)
class KeysInfo(BaseMetric):
    """You probably don't need this.

    This is a special section that contains information about the keys in the other sections.
    """

    section: ClassVar[Literal["keys_info"]] = "keys_info"


METRIC_TYPE_MAP = InvertableDict(
    {
        "run": Metric,
        "summary": Summary,
        "config": Config,
        "keys_info": KeysInfo,
        # Note: Tags is not in this map because it uses section="run"
        # Use Tags() directly or Metric("tags") to filter by tags
    }
)


@dataclass(frozen=True)
class Ordering:
    item: BaseMetric
    ascending: bool = True

    def to_key(self) -> SortKey:
        k = self.item.to_key()
        skk = SortKeyKey(section=k.section, name=k.name)
        return SortKey(key=skk, ascending=self.ascending)

    @classmethod
    def from_key(cls, key: SortKey) -> "Ordering":
        item = BaseMetric.from_key(key.key)
        return cls(item, key.ascending)


@dataclass
class FilterExpr:
    """A converted expression to be used in W&B Filters.

    Don't instantiate this class directly.  Instead, use one of the base metrics above
    (e.g. Metric, Summary, Config, etc) and use the comparison operators to create a FilterExpr

    For example:
      - Metric("loss") < 0.5; or
      - Config("model").isin(["resnet", "densenet"])
    """

    op: str
    key: BaseMetric
    value: Any

    def __init__(self, *args, **kwargs):
        raise RuntimeError(
            """Don't instantiate this class directly.  Instead, write an expression using the base metrics, e.g. Metric("loss") < 0.5"""
        )

    @classmethod
    def create(cls, op: str, key: BaseMetric, value: Any):
        key_cls = key.__class__
        mapped_name = _convert_be_to_fe_metric_name(key.name)
        new_key = key_cls(mapped_name)

        instance = cls.__new__(cls)
        instance.op = op
        instance.key = new_key
        instance.value = value
        return instance

    def __repr__(self) -> str:
        return f"({self.key} {OPERATOR_MAP[self.op]} {repr(self.value)})"

    def to_model(self) -> Filters:
        section = self.key.section
        name = _convert_fe_to_be_metric_name(self.key.name)

        return Filters(
            op=self.op,
            key=Key(section=section, name=name),
            value=self.value,
            disabled=False,
        )


def filters_tree_to_filter_expr(tree: Filters) -> List[FilterExpr]:
    def parse_filter(filter: Filters) -> Optional[FilterExpr]:
        if filter.key is None:
            return None
        metric_cls = METRIC_TYPE_MAP.get(filter.key.section, BaseMetric)
        mapped_name = _convert_be_to_fe_metric_name(filter.key.name)
        metric = metric_cls(mapped_name)
        return FilterExpr.create(filter.op, metric, filter.value)

    def parse_expression(expr: Filters) -> List[FilterExpr]:
        if expr.filters:
            filters = []
            for f in expr.filters:
                filters.extend(parse_expression(f))
            return filters
        else:
            return [f for f in [parse_filter(expr)] if f is not None]

    return parse_expression(tree)


def filter_expr_to_filters_tree(filters: List[FilterExpr]) -> Filters:
    def parse_key(metric: BaseMetric) -> Key:
        section = metric.section
        name = _convert_fe_to_be_metric_name(metric.name)
        return Key(section=section, name=name)

    def parse_filter(filter: FilterExpr) -> Filters:
        key = parse_key(filter.key)
        return Filters(op=filter.op, key=key, value=filter.value, disabled=False)

    return Filters(
        op="OR",
        filters=[
            Filters(
                op="AND", filters=[parse_filter(f) for f in filters if f is not None]
            )
        ],
    )


def string_to_filterexpr_list(filter_string: str) -> List[FilterExpr]:
    """Convert a string filter expression to a list of FilterExpr objects.

    This is a convenience function that combines expr_parsing.expr_to_filters()
    and filters_tree_to_filter_expr() to provide a direct string → FilterExpr list conversion.

    Args:
        filter_string: A Python-like filter expression string, e.g.,
            "Config('learning_rate') = 0.001 and State = 'finished'"

    Returns:
        A list of FilterExpr objects

    Example:
        >>> filters = string_to_filterexpr_list("Config('lr') = 0.001")
        >>> len(filters)
        1
        >>> filters[0].key.section
        'config'
    """
    from .reports.v2 import expr_parsing

    if not filter_string:
        return []

    # Convert string expression to internal Filters tree
    filters_tree = expr_parsing.expr_to_filters(filter_string)
    # Convert Filters tree to FilterExpr list
    return filters_tree_to_filter_expr(filters_tree)


def filterexpr_list_to_string(filters: List[FilterExpr]) -> str:
    """Convert a list of FilterExpr objects to a string filter expression.

    This is a convenience function that combines filter_expr_to_filters_tree()
    and expr_parsing.filters_to_expr() to provide a direct FilterExpr list → string conversion.

    Args:
        filters: A list of FilterExpr objects

    Returns:
        A Python-like filter expression string

    Example:
        >>> from wandb_workspaces import expr
        >>> filters = [expr.Config("learning_rate") == 0.001]
        >>> filterexpr_list_to_string(filters)
        'Config("learning_rate") == 0.001'
    """
    from .reports.v2 import expr_parsing

    if not filters:
        return ""

    # Convert FilterExpr list to internal Filters tree
    filters_tree = filter_expr_to_filters_tree(filters)
    # Convert Filters tree to string expression
    return expr_parsing.filters_to_expr(filters_tree)


def normalize_filters_to_string(instance):
    """Shared model validator that normalizes filters to string format.

    Converts List[FilterExpr] → str while preserving string inputs.
    This creates a unified internal representation across Workspaces and Reports.

    Args:
        instance: The model instance with a 'filters' attribute

    Returns:
        The instance with normalized filters

    Usage:
        @model_validator(mode="after")
        def convert_filterexpr_list_to_string(self):
            return normalize_filters_to_string(self)
    """
    if isinstance(instance.filters, list):
        # Convert FilterExpr list to string
        # This unifies internal representation as string
        filter_string = filterexpr_list_to_string(instance.filters)
        # Update the filters field
        object.__setattr__(instance, "filters", filter_string)
    return instance


def _convert_fe_to_be_metric_name(name: str) -> str:
    return FE_METRIC_NAME_MAP.get(name, name)


def _convert_be_to_fe_metric_name(name: str) -> str:
    return FE_METRIC_NAME_MAP.inv.get(name, name)


MetricType = Union[Metric, Summary, Config, Tags, KeysInfo]
