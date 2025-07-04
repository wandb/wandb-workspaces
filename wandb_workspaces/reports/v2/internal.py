"""JSONSchema for internal types.  Hopefully this is auto-generated one day!"""

import json
import random
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union
from typing import List as LList

from annotated_types import Annotated, Ge, Le, Len

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    root_validator,
    validator,
)
from pydantic.alias_generators import to_camel


def _generate_name(length: int = 12) -> str:
    """Generate a random name.

    This implementation roughly based the following snippet in core:
    https://github.com/wandb/core/blob/master/lib/js/cg/src/utils/string.ts#L39-L44.
    """

    # Borrowed from numpy: https://github.com/numpy/numpy/blob/v1.23.0/numpy/core/numeric.py#L2069-L2123
    def base_repr(number: int, base: int, padding: int = 0) -> str:
        digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if base > len(digits):
            raise ValueError("Bases greater than 36 not handled in base_repr.")
        elif base < 2:
            raise ValueError("Bases less than 2 not handled in base_repr.")

        num = abs(number)
        res = []
        while num:
            res.append(digits[num % base])
            num //= base
        if padding:
            res.append("0" * padding)
        if number < 0:
            res.append("-")
        return "".join(reversed(res or "0"))

    rand = random.random()
    rand = int(float(str(rand)[2:]))
    rand36 = base_repr(rand, 36)
    return rand36.lower()[:length]


hex_pattern = r"^#(?:[0-9a-fA-F]{3}){1,2}$"
rgb_pattern = r"^rgb\(\s*(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\s*,\s*(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\s*,\s*(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\s*\)$"
rgba_pattern = r"^rgba\(\s*(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\s*,\s*(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\s*,\s*(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\s*,\s*(1|0|0?\.\d+)\s*\)$"
ColorStrConstraints = StringConstraints(
    pattern=f"{hex_pattern}|{rgb_pattern}|{rgba_pattern}"
)

LinePlotStyle = Literal["line", "stacked-area", "pct-area"]
BarPlotStyle = Literal["bar", "boxplot", "violin"]
FontSize = Literal["small", "medium", "large", "auto"]
LegendPosition = Literal["north", "south", "east", "west"]
LegendOrientation = Literal["horizontal", "vertical"]
GroupAgg = Literal["mean", "min", "max", "median", "sum", "samples"]
GroupArea = Literal["minmax", "stddev", "stderr", "none", "samples"]
Mark = Literal["solid", "dashed", "dotted", "dotdash", "dotdotdash"]
Timestep = Literal["seconds", "minutes", "hours", "days"]
SmoothingType = Literal[
    "exponentialTimeWeighted", "exponential", "gaussian", "average", "none"
]
CodeCompareDiff = Literal["split", "unified"]
Range = Tuple[Optional[float], Optional[float]]
Language = Literal["javascript", "python", "css", "json", "html", "markdown", "yaml"]
Ops = Literal["OR", "AND", "=", "!=", "<=", ">=", "<", ">", "IN", "NIN", "=="]
TextLikeInternal = Union["InlineLatex", "InlineLink", "Paragraph", "Text"]
GalleryLink = Union["GalleryLinkReport", "GalleryLinkURL"]
ReportWidth = Literal["readable", "fixed", "fluid"]
PointVizMethod = Literal["bucketing-gorilla", "sampling"]
TooltipNumberOfRuns = Literal["single", "default", "all_runs"]


class TextLikeMixin:
    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        data["children"] = [c.model_dump() for c in self.children]
        return data

    @classmethod
    def model_validate(cls, data):
        d = deepcopy(data)
        children = []
        for c in d.get("children"):
            _type = c.get("type")
            if _type == "link":
                child = InlineLink.model_validate(c)
            elif _type == "latex":
                child = InlineLatex.model_validate(c)
            elif _type == "paragraph":
                child = Paragraph.model_validate(c)
            else:
                child = Text.model_validate(c)
            children.append(child)

        d["children"] = children
        obj = cls(**d)
        return obj


class ReportAPIBaseModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


class UnknownBlock(ReportAPIBaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )


class InlineModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="forbid",
    )


class Text(ReportAPIBaseModel):
    text: str = ""
    inline_code: Optional[bool] = None

    inline_comments: Optional[LList["InlineComment"]] = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        comments = self.inline_comments
        if comments is None:
            comments = []
        for comment in comments:
            ref_id = comment.ref_id
            data[f"inlineComment_{ref_id}"] = comment.model_dump()
        data.pop("inline_comments", None)
        return data

    @classmethod
    def model_validate(cls, data):
        d = deepcopy(data)
        obj = cls(**d)

        inline_comments = []
        for k, v in d.items():
            if k.startswith("inlineComment"):
                comment = InlineComment.model_validate(v)
                inline_comments.append(comment)
        obj.inline_comments = inline_comments
        return obj


class Project(ReportAPIBaseModel):
    name: Optional[str] = None
    # name: str = ""
    entity_name: str = ""
    id: Optional[str] = None


class PanelBankConfigSettings(ReportAPIBaseModel):
    auto_organize_prefix: int = 2
    show_empty_sections: bool = False
    sort_alphabetically: bool = False
    search_query: Optional[str] = None
    search_history: Optional[LList[Dict[Literal["query"], str]]] = None
    auto_expand_search_results: Optional[bool] = None


class FlowConfig(ReportAPIBaseModel):
    snap_to_columns: bool = True
    columns_per_page: int = 3
    rows_per_page: int = 2
    gutter_width: int = 16
    box_width: int = 460
    box_height: int = 300


class LocalPanelSettings(ReportAPIBaseModel):
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

    @computed_field
    @property
    def smoothing_active(self) -> bool:
        return self.smoothing_type != "none" or self.smoothing_weight != 0

    @computed_field
    @property
    def x_axis_active(self) -> bool:  # TODO: Maybe broken prop
        return (
            self.x_axis != "_step"
            or self.x_axis_min is not None
            or self.x_axis_max is not None
        )


class PanelBankConfigSectionsItem(ReportAPIBaseModel):
    name: str = "Hidden Panels"
    is_open: bool = False
    type: str = "flow"
    flow_config: FlowConfig = Field(default_factory=FlowConfig)
    sorted: int = 0
    local_panel_settings: LocalPanelSettings = Field(default_factory=LocalPanelSettings)
    panels: LList["PanelTypes"] = Field(default_factory=list)


class PanelBankConfig(ReportAPIBaseModel):
    state: int = 0
    settings: PanelBankConfigSettings = Field(default_factory=PanelBankConfigSettings)
    sections: LList[PanelBankConfigSectionsItem] = Field(
        default_factory=lambda: [PanelBankConfigSectionsItem()]
    )

    # Run keys are arbitrarily added here, so add some type checking for safety
    # All run keys have the shape (key:str, value:colour)
    @root_validator(pre=True)
    def check_arbitrary_keys(cls, values):  # noqa: N805
        fixed_keys = cls.__annotations__.keys()
        ignored_keys = {"ref"}
        for k, v in values.items():
            if k not in fixed_keys and k not in ignored_keys and not isinstance(v, str):
                raise ValueError(f"Arbitrary key '{k}' must be of type 'str'")
        return values


class PanelBankSectionConfig(ReportAPIBaseModel):
    name: Literal["Report Panels"] = "Report Panels"
    is_open: bool = False
    panels: LList["PanelTypes"] = Field(default_factory=list)
    type: Literal["grid"] = "grid"
    flow_config: FlowConfig = Field(default_factory=FlowConfig)
    sorted: int = 0
    local_panel_settings: LocalPanelSettings = Field(default_factory=LocalPanelSettings)
    pinned: Optional[bool] = None


class PanelGridMetadataPanels(ReportAPIBaseModel):
    views: dict = Field(
        default_factory=lambda: {"0": {"name": "Panels", "defaults": [], "config": []}}
    )
    tabs: list = Field(default_factory=lambda: ["0"])


class PanelGridMetadata(ReportAPIBaseModel):
    open_viz: bool = True
    open_run_set: Optional[int] = 0  # none is closed
    name: Literal["unused-name"] = "unused-name"
    run_sets: LList["Runset"] = Field(default_factory=lambda: [Runset()])
    hide_run_sets: bool = False
    panels: PanelGridMetadataPanels = Field(default_factory=PanelGridMetadataPanels)
    panel_bank_config: PanelBankConfig = Field(default_factory=PanelBankConfig)
    panel_bank_section_config: PanelBankSectionConfig = Field(
        default_factory=PanelBankSectionConfig
    )
    custom_run_colors: Dict[str, Union[str, dict]] = Field(default_factory=dict)
    # custom_run_colors: PanelGridCustomRunColors = Field(
    #     default_factory=PanelGridCustomRunColors
    # )


class Block(ReportAPIBaseModel): ...


class PanelGrid(Block):
    type: Literal["panel-grid"] = "panel-grid"
    children: LList[Text] = Field(default_factory=lambda: [Text()])
    metadata: PanelGridMetadata = Field(default_factory=PanelGridMetadata)


class RunsetSearch(ReportAPIBaseModel):
    query: str = ""
    is_regex: Optional[bool] = None


class RunFeed(ReportAPIBaseModel):
    version: int = 2
    column_visible: Dict[str, bool] = Field(default_factory=lambda: {"run:name": False})
    column_pinned: Dict[str, bool] = Field(default_factory=dict)
    column_widths: Dict[str, int] = Field(default_factory=dict)
    column_order: LList[str] = Field(default_factory=list)
    page_size: int = 10
    only_show_selected: bool = False


class Key(ReportAPIBaseModel):
    section: str = "summary"
    name: str = ""


class Filters(ReportAPIBaseModel):
    op: Ops = "OR"
    key: Optional[Key] = None
    filters: Optional[LList["Filters"]] = None
    value: Optional[Any] = None
    disabled: Optional[bool] = None
    current: Optional["Filters"] = None


class SortKeyKey(ReportAPIBaseModel):
    section: str = "run"
    name: str = "createdAt"


class SortKey(ReportAPIBaseModel):
    key: SortKeyKey = Field(default_factory=SortKeyKey)
    ascending: bool = False


class Sort(ReportAPIBaseModel):
    keys: LList[SortKey] = Field(default_factory=lambda: [SortKey()])


class RunsetSelections(ReportAPIBaseModel):
    root: int = 1
    bounds: LList = Field(default_factory=list)
    tree: LList[str] = Field(default_factory=list)


class Runset(ReportAPIBaseModel):
    id: str = _generate_name()
    run_feed: RunFeed = Field(default_factory=RunFeed)
    enabled: bool = True
    project: Optional[Project] = None
    name: str = "Run set"
    search: RunsetSearch = Field(default_factory=RunsetSearch)
    filters: Filters = Field(
        default_factory=lambda: Filters(filters=[Filters(op="AND")])
    )
    grouping: LList[Key] = Field(default_factory=list)
    sort: Sort = Field(default_factory=Sort)
    selections: RunsetSelections = Field(default_factory=RunsetSelections)
    expanded_row_addresses: list = Field(default_factory=list)


class CodeLine(ReportAPIBaseModel):
    type: Literal["code-line"] = "code-line"
    children: LList[TextLikeInternal] = Field(default_factory=lambda: [Text()])
    language: Optional[Language] = "python"


class Heading(TextLikeMixin, Block):
    type: Literal["heading"] = "heading"
    children: LList[TextLikeInternal] = Field(default_factory=lambda: [Text()])
    collapsed_children: Optional[LList["BlockTypes"]] = None
    level: int = 1


class InlineLatex(InlineModel):
    type: Literal["latex"] = "latex"
    children: LList[Text] = Field(default_factory=lambda: [Text()])
    content: str = ""


class InlineLink(TextLikeMixin, InlineModel):
    type: Literal["link"] = "link"
    url: str = "https://"
    children: LList[Text] = Field(default_factory=lambda: [Text()])


class Paragraph(TextLikeMixin, Block):
    type: Literal["paragraph"] = "paragraph"
    children: LList[TextLikeInternal] = Field(default_factory=lambda: [Text()])

    model_config = ConfigDict(
        alias_generator=to_camel,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="forbid",
    )

    @validator("children", pre=True, each_item=True)
    def parse_children(cls, v):  # noqa: N805
        if isinstance(v, BaseModel):
            v = v.model_dump()
        if isinstance(v, dict):
            if v.get("type") == "latex":
                return InlineLatex(**v)
            elif v.get("type") == "link":
                return InlineLink(**v)
        return Text(**v)


class BlockQuote(Block):
    type: Literal["block-quote"] = "block-quote"
    children: LList[TextLikeInternal] = Field(default_factory=lambda: [Text()])


class CodeBlock(Block):
    type: Literal["code-block"] = "code-block"
    children: LList[CodeLine] = Field(default_factory=lambda: [CodeLine()])
    language: Optional[Language] = "python"


class MarkdownBlock(Block):
    type: Literal["markdown-block"] = "markdown-block"
    children: LList[Text] = Field(default_factory=lambda: [Text()])
    content: str = ""


class LatexBlock(Block):
    type: Literal["latex"] = "latex"
    children: LList[Text] = Field(default_factory=lambda: [Text()])
    content: str = ""
    block: bool = True


class Image(Block):
    type: Literal["image"] = "image"
    children: LList[TextLikeInternal] = Field(default_factory=lambda: [Text()])
    url: str
    has_caption: bool


class ListItem(ReportAPIBaseModel):
    type: Literal["list-item"] = "list-item"
    children: LList[TextLikeInternal]
    ordered: Optional[bool] = None
    checked: Optional[bool] = None


class List(Block):
    type: Literal["list"] = "list"
    children: LList[ListItem] = Field(default_factory=lambda: [ListItem()])
    ordered: Optional[bool] = None


class CalloutLine(ReportAPIBaseModel):
    type: Literal["callout-line"] = "callout-line"
    children: LList[TextLikeInternal] = Field(default_factory=lambda: [Text()])


class CalloutBlock(Block):
    type: Literal["callout-block"] = "callout-block"
    children: LList[CalloutLine] = Field(default_factory=lambda: list)


class HorizontalRule(Block):
    type: Literal["horizontal-rule"] = "horizontal-rule"
    children: LList[Text] = Field(default_factory=lambda: [Text()])


class Video(Block):
    type: Literal["video"] = "video"
    url: str
    children: LList[Text] = Field(default_factory=lambda: [Text()])


class Spotify(Block):
    type: Literal["spotify"] = "spotify"
    spotify_type: Literal["track"] = "track"
    spotify_id: str = Field(..., alias="spotifyID")
    children: LList[Text] = Field(default_factory=lambda: [Text()])


class SoundCloud(Block):
    type: Literal["soundcloud"] = "soundcloud"
    html: str
    children: LList[Text] = Field(default_factory=lambda: [Text()])


class GalleryLinkReport(ReportAPIBaseModel):
    type: Literal["report"] = "report"
    id: str = ""


class GalleryLinkURL(ReportAPIBaseModel):
    type: Literal["url"] = "url"
    url: str = ""
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = Field(..., alias="imageURL")


class Gallery(Block):
    type: Literal["gallery"] = "gallery"
    children: LList[Text] = Field(default_factory=lambda: [Text()])
    links: Optional[LList[GalleryLink]] = None
    ids: Optional[LList[str]] = None


class TableOfContents(ReportAPIBaseModel):
    type: Literal["table-of-contents"] = "table-of-contents"
    children: LList[Text] = Field(default_factory=lambda: [Text()])


class Twitter(ReportAPIBaseModel):
    type: Literal["twitter"] = "twitter"
    children: LList[Text] = Field(default_factory=lambda: [Text()])
    html: str


class WeaveBlock(ReportAPIBaseModel):
    type: Literal["weave-panel"] = "weave-panel"
    children: LList[Text] = Field(default_factory=lambda: [Text()])
    config: dict = Field(default_factory=dict)


class InlineComment(ReportAPIBaseModel):
    ref_id: str = Field(..., alias="refID")
    thread_id: str = Field(..., alias="threadID")
    comment_id: str = Field(..., alias="commentID")


class Spec(ReportAPIBaseModel):
    version: int = 5
    panel_settings: dict = Field(default_factory=dict)
    blocks: LList["BlockTypes"] = Field(default_factory=list)
    width: str = "readable"
    authors: list = Field(default_factory=list)
    discussion_threads: list = Field(default_factory=list)


class ReportViewspec(ReportAPIBaseModel):
    id: str = ""
    name: str = ""
    display_name: str = ""
    description: str = ""
    project: Project = Field(default_factory=Project)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    spec: Spec = Field(default_factory=Spec)

    @validator("spec", pre=True)
    def parse_json(cls, v):  # noqa: N805
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("invalid json")
        return v


class Layout(ReportAPIBaseModel):
    x: int = 0
    y: int = 0
    w: int = 8
    h: int = 6


class Panel(ReportAPIBaseModel):
    id: str = Field("", alias="__id__")
    layout: Layout = Field(default_factory=Layout)


class MediaBrowserConfig(ReportAPIBaseModel):
    column_count: Optional[int] = None
    media_keys: LList[str] = Field(default_factory=list)


class MediaBrowser(Panel):
    view_type: Literal["Media Browser"] = "Media Browser"
    config: MediaBrowserConfig = Field(default_factory=MediaBrowserConfig)


class MarkdownPanelConfig(ReportAPIBaseModel):
    value: str


class MarkdownPanel(Panel):
    view_type: Literal["Markdown Panel"] = "Markdown Panel"
    config: MarkdownPanelConfig


class LinePlotConfig(ReportAPIBaseModel):
    chart_title: Optional[str] = None
    x_axis: Optional[str] = None
    metrics: LList[str] = Field(default_factory=list)
    x_axis_min: Optional[float] = None
    x_axis_max: Optional[float] = None
    y_axis_min: Optional[float] = None
    y_axis_max: Optional[float] = None
    x_log_scale: Optional[bool] = None
    y_log_scale: Optional[bool] = None
    x_axis_title: Optional[str] = None
    y_axis_title: Optional[str] = None
    ignore_outliers: Optional[bool] = None
    group_by: Optional[str] = None
    group_agg: Optional[GroupAgg] = None
    group_area: Optional[GroupArea] = None
    smoothing_weight: Optional[float] = None
    smoothing_type: Optional[SmoothingType] = None
    show_original_after_smoothing: Optional[bool] = None
    limit: Optional[int] = None
    expressions: Optional[LList[str]] = None
    plot_type: Optional[LinePlotStyle] = None
    font_size: Optional[FontSize] = None
    legend_position: Optional[LegendPosition] = None
    legend_template: Optional[str] = None
    aggregate: Optional[bool] = None
    x_expression: Optional[str] = None

    override_line_widths: Optional[dict] = None
    override_colors: Optional[dict] = None
    override_series_titles: Optional[dict] = None
    legend_fields: Optional[LList[str]] = None

    # there are more here...


class LinePlot(Panel):
    view_type: Literal["Run History Line Plot"] = "Run History Line Plot"
    config: LinePlotConfig = Field(default_factory=LinePlotConfig)


class GradientPoint(ReportAPIBaseModel):
    color: Annotated[str, ColorStrConstraints]
    offset: Annotated[float, Ge(0), Le(100)] = 0


class ScatterPlotConfig(ReportAPIBaseModel):
    chart_title: Optional[str] = None
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    z_axis: Optional[str] = None
    x_axis_min: Optional[float] = None
    x_axis_max: Optional[float] = None
    y_axis_min: Optional[float] = None
    y_axis_max: Optional[float] = None
    z_axis_min: Optional[float] = None
    z_axis_max: Optional[float] = None
    x_axis_log_scale: Optional[bool] = None
    y_axis_log_scale: Optional[bool] = None
    z_axis_log_scale: Optional[bool] = None
    show_min_y_axis_line: Optional[bool] = None
    show_max_y_axis_line: Optional[bool] = None
    show_avg_y_axis_line: Optional[bool] = None
    legend_template: Optional[str] = None
    custom_gradient: Optional[LList[GradientPoint]] = None
    font_size: Optional[FontSize] = None
    show_linear_regression: Optional[bool] = None


class ScatterPlot(Panel):
    view_type: Literal["Scatter Plot"] = "Scatter Plot"
    config: ScatterPlotConfig = Field(default_factory=ScatterPlotConfig)


class BarPlotConfig(ReportAPIBaseModel):
    chart_title: Optional[str] = None
    metrics: LList[str] = Field(default_factory=list)
    vertical: bool = False
    x_axis_min: Optional[float] = None
    x_axis_max: Optional[float] = None
    x_axis_title: Optional[str] = None
    y_axis_title: Optional[str] = None
    group_by: Optional[str] = None
    group_agg: Optional[GroupAgg] = None
    group_area: Optional[GroupArea] = None
    limit: Optional[int] = None
    bar_limit: Optional[int] = None
    expressions: Optional[LList[str]] = None
    legend_template: Optional[str] = None
    font_size: Optional[FontSize] = None
    override_series_titles: Optional[dict] = None
    override_colors: Optional[dict] = None
    aggregate: Optional[bool] = None


class BarPlot(Panel):
    view_type: Literal["Bar Chart"] = "Bar Chart"
    config: BarPlotConfig = Field(default_factory=BarPlotConfig)


class ScalarChartConfig(ReportAPIBaseModel):
    chart_title: Optional[str] = None
    metrics: LList[str] = Field(default_factory=list)
    group_agg: Optional[GroupAgg] = None
    group_area: Optional[GroupArea] = None
    expressions: Optional[LList[str]] = None
    legend_template: Optional[str] = None
    font_size: Optional[FontSize] = None


class ScalarChart(Panel):
    view_type: Literal["Scalar Chart"] = "Scalar Chart"
    config: ScalarChartConfig = Field(default_factory=ScalarChartConfig)


class CodeComparerConfig(ReportAPIBaseModel):
    diff: CodeCompareDiff = "split"


class CodeComparer(Panel):
    view_type: Literal["Code Comparer"] = "Code Comparer"
    config: CodeComparerConfig = Field(default_factory=CodeComparerConfig)


class Column(ReportAPIBaseModel):
    accessor: str
    display_name: Optional[str] = None
    inverted: Optional[bool] = None
    log: Optional[bool] = None


class ParallelCoordinatesPlotConfig(ReportAPIBaseModel):
    chart_title: Optional[str] = None
    columns: LList[Column] = Field(default_factory=list)
    custom_gradient: Optional[LList[GradientPoint]] = None
    font_size: Optional[FontSize] = None


class ParallelCoordinatesPlot(Panel):
    view_type: Literal["Parallel Coordinates Plot"] = "Parallel Coordinates Plot"
    config: ParallelCoordinatesPlotConfig = Field(
        default_factory=ParallelCoordinatesPlotConfig
    )


class ParameterConf(ReportAPIBaseModel):
    version: int = 2
    column_visible: dict = Field(default_factory=dict)


class ParameterImportancePlotConfig(ReportAPIBaseModel):
    target_key: str
    columns_pinned: dict = Field(default_factory=dict)
    column_widths: dict = Field(default_factory=dict)
    column_order: LList[str] = Field(default_factory=list)
    page_size: int = 10
    only_show_selected: bool = False


class ParameterImportancePlot(Panel):
    view_type: Literal["Parameter Importance"] = "Parameter Importance"
    config: ParameterImportancePlotConfig


class RunComparerConfig(ReportAPIBaseModel):
    diff_only: Optional[Literal["split", True]] = None


class RunComparer(Panel):
    view_type: Literal["Run Comparer"] = "Run Comparer"
    config: RunComparerConfig


class QueryField(ReportAPIBaseModel):
    name: str = "runSets"
    args: Optional[LList["QueryField"]] = None
    fields: Optional[LList["QueryField"]] = None
    value: Optional[Union[list, float, str]] = None


class UserQuery(ReportAPIBaseModel):
    query_fields: Annotated[LList[QueryField], Len(min_length=1, max_length=1)] = Field(
        default_factory=lambda: [QueryField()]
    )


class Vega2ConfigTransform(ReportAPIBaseModel):
    name: Literal["tableWithLeafColNames"] = "tableWithLeafColNames"


class Vega2Config(ReportAPIBaseModel):
    transform: Vega2ConfigTransform = Field(default_factory=Vega2ConfigTransform)
    user_query: UserQuery = Field(default_factory=UserQuery)
    panel_def_id: str = ""
    field_settings: dict = Field(default_factory=dict)
    string_settings: dict = Field(default_factory=dict)


class Vega2(Panel):
    view_type: Literal["Vega2"] = "Vega2"
    config: Vega2Config = Field(default_factory=Vega2Config)


class UnknownPanel(ReportAPIBaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )


class WeavePanel(Panel):
    view_type: Literal["Weave"] = "Weave"
    config: dict


PanelTypes = Union[
    LinePlot,
    ScatterPlot,
    ScalarChart,
    BarPlot,
    CodeComparer,
    ParallelCoordinatesPlot,
    ParameterImportancePlot,
    RunComparer,
    MediaBrowser,
    MarkdownPanel,
    Vega2,
    WeavePanel,
    UnknownPanel,
]

BlockTypes = Union[
    Heading,
    Paragraph,
    CodeBlock,
    MarkdownBlock,
    LatexBlock,
    Image,
    List,
    CalloutBlock,
    Video,
    HorizontalRule,
    Spotify,
    SoundCloud,
    Gallery,
    PanelGrid,
    TableOfContents,
    BlockQuote,
    Twitter,
    WeaveBlock,
    UnknownBlock,
]

block_type_mapping: Dict[str, BlockTypes] = {
    "twitter": Twitter,
    "heading": Heading,
    "paragraph": Paragraph,
    "code-block": CodeBlock,
    "markdown-block": MarkdownBlock,
    "latex-block": LatexBlock,
    "image": Image,
    "list": List,
    "callout-block": CalloutBlock,
    "video": Video,
    "horziontal-rule": HorizontalRule,
    "spotify": Spotify,
    "soundcloud": SoundCloud,
    "gallery": Gallery,
    "panel-grid": PanelGrid,
    "table-of-contents": TableOfContents,
    "block-quote": BlockQuote,
}


def _get_weave_block_inputs(config: dict) -> dict:
    return config["panelConfig"]["exp"]["fromOp"]["inputs"]


def _get_weave_panel_inputs(config: dict) -> dict:
    return config["panel2Config"]["exp"]["fromOp"]["inputs"]
