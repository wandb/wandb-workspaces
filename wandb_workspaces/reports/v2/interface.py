"""
Python library for programmatically working with W&B Reports API.

```python
import wandb_workspaces.reports.v2 as wr

report = wr.Report(
    entity="entity",
    project="project",
    title="An amazing title",
    description="A descriptive description.",
)

blocks = [
    wr.PanelGrid(
        panels=[
            wr.LinePlot(x="time", y="velocity"),
            wr.ScatterPlot(x="time", y="acceleration"),
        ]
    )
]

report.blocks = blocks
report.save()
```

"""

import base64
import os
from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple, Union
from typing import List as LList

from annotated_types import Annotated, Ge, Le

try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal

from urllib.parse import urlparse, urlunparse

import wandb
from pydantic import ConfigDict, Field, validator
from pydantic.dataclasses import dataclass

from . import expr_parsing, gql, internal
from .internal import (
    CodeCompareDiff,
    FontSize,
    GroupAgg,
    GroupArea,
    Language,
    LegendPosition,
    LinePlotStyle,
    Range,
    ReportWidth,
    SmoothingType,
)

TextLike = Union[str, "TextWithInlineComments", "Link", "InlineLatex", "InlineCode"]
TextLikeField = Union[TextLike, LList[TextLike]]
SpecialMetricType = Union["Config", "SummaryMetric", "Metric"]
MetricType = Union[str, SpecialMetricType]
SummaryOrConfigOnlyMetric = Union[str, "Config", "SummaryMetric", "Metric"]
RunId = str


dataclass_config = ConfigDict(validate_assignment=True, extra="forbid", slots=True)


def _is_not_all_none(v):
    if v is None or v == "":
        return False
    if isinstance(v, Iterable) and not isinstance(v, str):
        return any(v not in (None, "") for v in v)
    return True


def _is_not_internal(k):
    return not k.startswith("_")


@dataclass(config=dataclass_config, repr=False)
class Base:
    def __repr__(self):
        fields = (
            f"{k}={v!r}"
            for k, v in self.__dict__.items()
            if (_is_not_all_none(v) and _is_not_internal(k))
        )
        fields_str = ", ".join(fields)
        return f"{self.__class__.__name__}({fields_str})"

    def __rich_repr__(self):
        for k, v in self.__dict__.items():
            if _is_not_all_none(v) and _is_not_internal(k):
                yield k, v

    @property
    def _model(self):
        return self.__to_model()

    @property
    def _spec(self):
        return self._model.model_dump(by_alias=True, exclude_none=True)


@dataclass(config=dataclass_config, frozen=True)
class RunsetGroupKey:
    """
    Groups runsets by a metric type and value. Part of a `RunsetGroup`.
    Specify the metric type and value to group by as key-value pairs.

    Attributes:
        key (Type[str] | Type[Config] | Type[SummaryMetric] | Type[Metric]): The metric type to group by.
        value (str): The value of the metric to group by.
    """

    key: MetricType
    value: str


@dataclass(config=dataclass_config, frozen=True)
class RunsetGroup:
    """UI element that shows a group of runsets.

    Attributes:
        runset_name (str): The name of the runset.
        keys (Tuple[RunsetGroupKey, ...]): The keys to group by.
            Pass in one or more `RunsetGroupKey`
            objects to group by.

    """

    runset_name: str
    keys: Tuple[RunsetGroupKey, ...]


@dataclass(config=dataclass_config, frozen=True)
class Metric:
    """
    A metric to display in a report that
    is logged in your project.

    Attributes:
        name(str): The name of the metric.
    """

    name: str


@dataclass(config=dataclass_config, frozen=True)
class Config:
    """
    Metrics logged to a run's config object.
    Config objects are commonly logged using `run.config[name] = ...`
    or passing a config as a dictionary of key-value pairs,
    where the key is the name of the metric and the value is
    the value of that metric.

    Attributes:
        name (str): The name of the metric.
    """

    name: str


@dataclass(config=dataclass_config, frozen=True)
class SummaryMetric:
    """A summary metric to display in a report.

    Attributes:
        name (str): The name of the metric.
    """

    name: str


@dataclass(config=dataclass_config, repr=False)
class Layout(Base):
    """The layout of a panel in a report. Adjusts the size and position of the panel.

    Attributes:
        x (int): The x position of the panel.
        y (int): The y position of the panel.
        w (int): The width of the panel.
        h (int): The height of the panel.
    """

    x: int = 0
    y: int = 0
    w: int = 8
    h: int = 6

    def _to_model(self):
        return internal.Layout(x=self.x, y=self.y, w=self.w, h=self.h)

    @classmethod
    def _from_model(cls, model: internal.Layout):
        return cls(x=model.x, y=model.y, w=model.w, h=model.h)


@dataclass(config=dataclass_config, repr=False)
class Block(Base):
    """
    INTERNAL: This class is not for public use.
    """


@dataclass(config=ConfigDict(validate_assignment=True, extra="allow", slots=True))
class UnknownBlock(Block):
    """
    INTERNAL: This class is not for public use.
    """

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        attributes = ", ".join(
            f"{key}={value!r}" for key, value in self.__dict__.items()
        )
        return f"{class_name}({attributes})"

    def _to_model(self):
        d = self.__dict__
        return internal.UnknownBlock.model_validate(d)

    @classmethod
    def _from_model(cls, model: internal.UnknownBlock):
        d = model.model_dump()
        return cls(**d)


@dataclass(config=dataclass_config, repr=False)
class TextWithInlineComments(Base):
    """A block of text with inline comments.

    Attributes:
        text (str): The text of the block.
    """

    text: str

    _inline_comments: Optional[LList[internal.InlineComment]] = Field(
        default_factory=lambda: None, repr=False
    )


@dataclass(config=dataclass_config, repr=False)
class Heading(Block):
    @classmethod
    def _from_model(cls, model: internal.Heading):
        text = _internal_children_to_text(model.children)

        blocks = None
        if model.collapsed_children:
            blocks = [_lookup(b) for b in model.collapsed_children]

        if model.level == 1:
            return H1(text=text, collapsed_blocks=blocks)
        if model.level == 2:
            return H2(text=text, collapsed_blocks=blocks)
        if model.level == 3:
            return H3(text=text, collapsed_blocks=blocks)


@dataclass(config=dataclass_config, repr=False)
class H1(Heading):
    """An H1 heading with the text specified.

    Attributes:
        text (str): The text of the heading.
        collapsed_blocks (Optional[LList["BlockTypes"]]): The blocks to show when the heading is collapsed.
    """

    text: TextLikeField = ""
    collapsed_blocks: Optional[LList["BlockTypes"]] = None

    def _to_model(self):
        collapsed_children = self.collapsed_blocks
        if collapsed_children is not None:
            collapsed_children = [b._to_model() for b in collapsed_children]

        return internal.Heading(
            level=1,
            children=_text_to_internal_children(self.text),
            collapsed_children=collapsed_children,
        )


@dataclass(config=dataclass_config, repr=False)
class H2(Heading):
    """An H2 heading with the text specified.

    Attributes:
        text (str): The text of the heading.
        collapsed_blocks (Optional[LList["BlockTypes"]]): One or more blocks to
            show when the heading is collapsed.
    """

    text: TextLikeField = ""
    collapsed_blocks: Optional[LList["BlockTypes"]] = None

    def _to_model(self):
        collapsed_children = self.collapsed_blocks
        if collapsed_children is not None:
            collapsed_children = [b._to_model() for b in collapsed_children]

        return internal.Heading(
            level=2,
            children=_text_to_internal_children(self.text),
            collapsed_children=collapsed_children,
        )


@dataclass(config=dataclass_config, repr=False)
class H3(Heading):
    """An H3 heading with the text specified.

    Attributes:
        text (str): The text of the heading.
        collapsed_blocks (Optional[LList["BlockTypes"]]): One or more blocks to
            show when the heading is collapsed.
    """

    text: TextLikeField = ""
    collapsed_blocks: Optional[LList["BlockTypes"]] = None

    def _to_model(self):
        collapsed_children = self.collapsed_blocks
        if collapsed_children is not None:
            collapsed_children = [b._to_model() for b in collapsed_children]

        return internal.Heading(
            level=3,
            children=_text_to_internal_children(self.text),
            collapsed_children=collapsed_children,
        )


@dataclass(config=dataclass_config, repr=False)
class Link(Base):
    """A link to a URL.

    Attributes:
        text (Union[str, TextWithInlineComments]): The text of the link.
        url (str): The URL the link points to.
    """

    text: Union[str, TextWithInlineComments]
    url: str

    _inline_comments: Optional[LList[internal.InlineComment]] = Field(
        default_factory=lambda: None, init=False, repr=False
    )


@dataclass(config=dataclass_config, repr=False)
class InlineLatex(Base):
    """Inline LaTeX markdown. Does not add newline
    character after the LaTeX markdown.

    Attributes:
        text (str): LaTeX markdown you want to appear in the report.
    """

    text: str


@dataclass(config=dataclass_config, repr=False)
class InlineCode(Base):
    """Inline code. Does not add newline
    character after code.

    Attributes:
        text (str): The code you want to appear in the report.
    """

    text: str


@dataclass(config=dataclass_config, repr=False)
class P(Block):
    """A paragraph of text.

    Attributes:
        text (str): The text of the paragraph.
    """

    text: TextLikeField = ""

    def _to_model(self):
        children = _text_to_internal_children(self.text)
        return internal.Paragraph(children=children)

    @classmethod
    def _from_model(cls, model: internal.Paragraph):
        pieces = _internal_children_to_text(model.children)
        return cls(text=pieces)


@dataclass(config=dataclass_config, repr=False)
class ListItem(Base):
    """
    INTERNAL: This class is not for public use.
    """

    @classmethod
    def _from_model(cls, model: internal.ListItem):
        text = _internal_children_to_text(model.children)
        if model.checked is not None:
            return CheckedListItem(text=text, checked=model.checked)
        return text
        # if model.ordered is not None:
        #     return OrderedListItem(text=text)
        # return UnorderedListItem(text=text)


@dataclass(config=dataclass_config, repr=False)
class CheckedListItem(Base):
    """A list item with a checkbox. Add one or more `CheckedListItem` within `CheckedList`.

    Attributes:
        text (str): The text of the list item.
        checked (bool): Whether the checkbox is checked. By default, set to `False`.
    """

    text: TextLikeField = ""
    checked: bool = False

    def _to_model(self):
        return internal.ListItem(
            children=[
                internal.Paragraph(children=_text_to_internal_children(self.text))
            ],
            checked=self.checked,
        )


@dataclass(config=dataclass_config, repr=False)
class OrderedListItem(Base):
    """A list item in an ordered list.

    Attributes:
        text (str): The text of the list item.
    """

    text: TextLikeField = ""

    def _to_model(self):
        return internal.ListItem(
            children=[
                internal.Paragraph(children=_text_to_internal_children(self.text))
            ],
            ordered=True,
        )


@dataclass(config=dataclass_config, repr=False)
class UnorderedListItem(Base):
    """A list item in an unordered list.

    Attributes:
        text (str): The text of the list item.
    """

    text: TextLikeField = ""

    def _to_model(self):
        return internal.ListItem(
            children=[
                internal.Paragraph(children=_text_to_internal_children(self.text))
            ],
        )


@dataclass(config=dataclass_config, repr=False)
class List(Block):
    """
    INTERNAL: This class is not for public use.
    """

    @classmethod
    def _from_model(cls, model: internal.List):
        if not model.children:
            return UnorderedList()

        item = model.children[0]
        items = [ListItem._from_model(x) for x in model.children]
        if item.checked is not None:
            return CheckedList(items=items)

        if item.ordered is not None:
            return OrderedList(items=items)

        # else unordered
        return UnorderedList(items=items)


@dataclass(config=dataclass_config, repr=False)
class CheckedList(List):
    """A list of items with checkboxes. Add one or more `CheckedListItem` within `CheckedList`.

    Attributes:
        items (LList[CheckedListItem]): A list of one or more `CheckedListItem` objects.
    """

    items: LList[CheckedListItem] = Field(default_factory=lambda: [CheckedListItem()])

    def _to_model(self):
        items = [x._to_model() for x in self.items]
        return internal.List(children=items)


@dataclass(config=dataclass_config, repr=False)
class OrderedList(List):
    """A list of items in a numbered list.

    Attributes:
        items (LList[str]): A list of one or more `OrderedListItem` objects.
    """

    items: LList[str] = Field(default_factory=lambda: [""])

    def _to_model(self):
        children = [OrderedListItem(li)._to_model() for li in self.items]
        return internal.List(children=children, ordered=True)


@dataclass(config=dataclass_config, repr=False)
class UnorderedList(List):
    """A list of items in a bulleted list.

    Attributes:
        items (LList[str]): A list of one or more `UnorderedListItem` objects.
    """

    items: LList[str] = Field(default_factory=lambda: [""])

    def _to_model(self):
        children = [UnorderedListItem(li)._to_model() for li in self.items]
        return internal.List(children=children)


@dataclass(config=dataclass_config, repr=False)
class BlockQuote(Block):
    """A block of quoted text.

    Attributes:
        text (str): The text of the block quote.
    """

    text: TextLikeField = ""

    def _to_model(self):
        return internal.BlockQuote(children=_text_to_internal_children(self.text))

    @classmethod
    def _from_model(cls, model: internal.BlockQuote):
        return cls(text=_internal_children_to_text(model.children))


@dataclass(config=dataclass_config, repr=False)
class CodeBlock(Block):
    """A block of code.

    Attributes:
        code (str): The code in the block.
        language (Optional[Language]): The language of the code. Language specified
            is used for syntax highlighting. By default, set to "python". Options include
            'javascript', 'python', 'css', 'json', 'html', 'markdown', 'yaml'.
    """

    code: TextLikeField = ""
    language: Optional[Language] = "python"

    def _to_model(self):
        return internal.CodeBlock(
            children=[
                internal.CodeLine(
                    children=_text_to_internal_children(self.code),
                    language=self.language,
                )
            ],
            language=self.language,
        )

    @classmethod
    def _from_model(cls, model: internal.CodeBlock):
        # Aggregate all lines of code into a single multiline string or TextLikeField
        lines = []
        for code_line in model.children:
            # code_line.children contains internal.Text nodes for each line
            line_text = _internal_children_to_text(code_line.children)
            lines.append(line_text)

        # If we have multiple lines, join them with newlines
        if len(lines) == 1:
            code = lines[0]
        else:
            # For multiple lines, we need to join them properly
            # If all lines are strings, join with newlines
            if all(isinstance(line, str) for line in lines):
                code = "\n".join(lines)
            else:
                # If we have mixed content, we need to preserve the structure
                # This is a complex case - for now, convert to string representation
                text_parts = []
                for i, line in enumerate(lines):
                    if isinstance(line, str):
                        text_parts.append(line)
                    elif isinstance(line, list):
                        # Handle list of mixed content
                        line_parts = []
                        for item in line:
                            if isinstance(item, str):
                                line_parts.append(item)
                            else:
                                # Preserve the original object (InlineCode, etc.)
                                line_parts.append(item)
                        if len(line_parts) == 1:
                            text_parts.append(line_parts[0])
                        else:
                            text_parts.extend(line_parts)
                    else:
                        text_parts.append(line)

                    # Add newline between lines (except for the last line)
                    if i < len(lines) - 1:
                        text_parts.append("\n")

                # If we have a single item, return it directly
                if len(text_parts) == 1:
                    code = text_parts[0]
                else:
                    code = text_parts

        return cls(code=code, language=model.language)


@dataclass(config=dataclass_config, repr=False)
class MarkdownBlock(Block):
    """A block of markdown text. Useful if you want to write text
    that uses common markdown syntax.

    Attributes:
        text (str): The markdown text.
    """

    text: str = ""

    def _to_model(self):
        return internal.MarkdownBlock(content=self.text)

    @classmethod
    def _from_model(cls, model: internal.MarkdownBlock):
        return cls(text=model.content)


@dataclass(config=dataclass_config, repr=False)
class LatexBlock(Block):
    """A block of LaTeX text.

    Attributes:
        text (str): The LaTeX text.
    """

    text: str = ""

    def _to_model(self):
        return internal.LatexBlock(content=self.text)

    @classmethod
    def _from_model(cls, model: internal.LatexBlock):
        return cls(text=model.content)


@dataclass(config=dataclass_config, repr=False)
class Image(Block):
    """A block that renders an image.

    Attributes:
        url (str): The URL of the image.
        caption (str): The caption of the image.
            Caption appears underneath the image.
    """

    url: str = "https://raw.githubusercontent.com/wandb/assets/main/wandb-logo-yellow-dots-black-wb.svg"
    caption: TextLikeField = ""

    def _to_model(self):
        has_caption = False
        children = _text_to_internal_children(self.caption)
        if children:
            has_caption = True

        return internal.Image(children=children, url=self.url, has_caption=has_caption)

    @classmethod
    def _from_model(cls, model: internal.Image):
        caption = _internal_children_to_text(model.children)
        return cls(url=model.url, caption=caption)


@dataclass(config=dataclass_config, repr=False)
class CalloutBlock(Block):
    """A block of callout text.

    Attributes:
        text (str): The callout text.
    """

    text: TextLikeField = ""

    def _to_model(self):
        return internal.CalloutBlock(
            children=[
                internal.CalloutLine(children=_text_to_internal_children(self.text))
            ]
        )

    @classmethod
    def _from_model(cls, model: internal.CalloutBlock):
        text = _internal_children_to_text(model.children[0].children)
        return cls(text=text)


@dataclass(config=dataclass_config, repr=False)
class HorizontalRule(Block):
    """HTML horizontal line."""

    def _to_model(self):
        return internal.HorizontalRule()

    @classmethod
    def _from_model(cls, model: internal.HorizontalRule):
        return cls()


@dataclass(config=dataclass_config, repr=False)
class Video(Block):
    """A block that renders a video.

    Attributes:
        url (str): The URL of the video.
    """

    url: str = "https://www.youtube.com/watch?v=krWjJcW80_A"

    def _to_model(self):
        return internal.Video(url=self.url)

    @classmethod
    def _from_model(cls, model: internal.Video):
        return cls(url=model.url)


@dataclass(config=dataclass_config, repr=False)
class Spotify(Block):
    """A block that renders a Spotify player.

    Attributes:
        spotify_id (str): The Spotify ID of the track or playlist.
    """

    spotify_id: str

    def _to_model(self):
        return internal.Spotify(spotify_id=self.spotify_id)

    @classmethod
    def _from_model(cls, model: internal.Spotify):
        return cls(spotify_id=model.spotify_id)


@dataclass(config=dataclass_config, repr=False)
class SoundCloud(Block):
    """A block that renders a SoundCloud player.

    Attributes:
        html (str): The HTML code to embed the SoundCloud player.
    """

    html: str

    def _to_model(self):
        return internal.SoundCloud(html=self.html)

    @classmethod
    def _from_model(cls, model: internal.SoundCloud):
        return cls(html=model.html)


@dataclass(config=dataclass_config, repr=False)
class GalleryReport(Base):
    """A reference to a report in the gallery.

    Attributes:
        report_id (str): The ID of the report.
    """

    report_id: str


@dataclass(config=dataclass_config, repr=False)
class GalleryURL(Base):
    """A URL to an external resource.

    Attributes:
        url (str): The URL of the resource.
        title (Optional[str]): The title of the resource.
        description (Optional[str]): The description of the resource.
        image_url (Optional[str]): The URL of an image to display.
    """

    url: str  # app accepts non-standard URL unfortunately
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None


@dataclass(config=dataclass_config, repr=False)
class Gallery(Block):
    """
    A block that renders a gallery of reports and URLs.

    Attributes:
        items (List[Union[`GalleryReport`, `GalleryURL`]]): A list of
            `GalleryReport` and `GalleryURL` objects.
    """

    items: LList[Union[GalleryReport, GalleryURL]] = Field(default_factory=list)

    def _to_model(self):
        links = []
        for x in self.items:
            if isinstance(x, GalleryReport):
                link = internal.GalleryLinkReport(id=x.report_id)
            elif isinstance(x, GalleryURL):
                link = internal.GalleryLinkURL(
                    url=x.url,
                    title=x.title,
                    description=x.description,
                    image_url=x.image_url,
                )
            links.append(link)

        return internal.Gallery(links=links)

    @classmethod
    def _from_model(cls, model: internal.Gallery):
        items = []
        if model.ids:
            items = [GalleryReport(x) for x in model.ids]
        elif model.links:
            for x in model.links:
                if isinstance(x, internal.GalleryLinkReport):
                    item = GalleryReport(report_id=x.id)
                elif isinstance(x, internal.GalleryLinkURL):
                    item = GalleryURL(
                        url=x.url,
                        title=x.title,
                        description=x.description,
                        image_url=x.image_url,
                    )
                items.append(item)

        return cls(items=items)


@dataclass(config=dataclass_config, repr=False)
class OrderBy(Base):
    """A metric to order by.

    Attributes:
        name (str): The name of the metric.
        ascending (bool): Whether to sort in ascending order.
            By default set to `False`.
    """

    name: MetricType
    ascending: bool = False

    def _to_model(self):
        return internal.SortKey(
            key=internal.SortKeyKey(name=_metric_to_backend(self.name)),
            ascending=self.ascending,
        )

    @classmethod
    def _from_model(cls, model: internal.SortKey):
        return cls(
            name=_metric_to_frontend(model.key.name),
            ascending=model.ascending,
        )


@dataclass(config=dataclass_config, repr=False)
class Runset(Base):
    """A set of runs to display in a panel grid.

    Attributes:
        entity (str): An entity that owns or has the correct
            permissions to the project where the runs are stored.
        project (str): The name of the project were the runs are stored.
        name (str): The name of the run set. Set to `Run set` by default.
        query (str): A query string to filter runs.
        filters (Optional[str]): A filter string to filter runs.
        groupby (LList[str]): A list of metric names to group by. Supported formats are:
            - "group" or "run.group" to group by a run attribute
            - "config.param" to group by a config parameter
            - "summary.metric" to group by a summary metric
        order (LList[OrderBy]): A list of `OrderBy` objects to order by.
        custom_run_colors (LList[OrderBy]): A dictionary mapping run IDs to colors.
    """

    entity: str = ""
    project: str = ""
    name: str = "Run set"
    query: str = ""
    filters: Optional[str] = ""
    groupby: LList[str] = Field(default_factory=list)
    order: LList[OrderBy] = Field(
        default_factory=lambda: [OrderBy("CreatedTimestamp", ascending=False)]
    )

    # this field does not get exported to model, but is used in PanelGrid
    custom_run_colors: Dict[Union[str, Tuple[MetricType, ...]], str] = Field(
        default_factory=dict
    )

    _id: str = Field(default_factory=internal._generate_name, init=False, repr=False)

    def _to_model(self):
        project = None

        if self.entity and self.project:
            # Look up project internal ID
            r = _get_api().client.execute(
                gql.projectInternalId,
                variable_values={
                    "entityName": self.entity,
                    "projectName": self.project,
                },
            )
            if r.get("project"):
                project = internal.Project(
                    entity_name=self.entity,
                    name=self.project,
                    id=r["project"]["internalId"],
                )
            else:
                raise ValueError(
                    f"Run set '{self.name}' project '{self.entity}/{self.project}' not found. "
                    "Please verify that the entity and project names are correct and that you have access to this project."
                )

        obj = internal.Runset(
            project=project,
            name=self.name,
            filters=expr_parsing.expr_to_filters(self.filters),
            grouping=[expr_parsing.groupby_str_to_key(g) for g in self.groupby],
            sort=internal.Sort(keys=[o._to_model() for o in self.order]),
        )
        obj.id = self._id
        return obj

    @classmethod
    def _from_model(cls, model: internal.Runset):
        entity = ""
        project = ""

        p = model.project
        if p is not None:
            if p.entity_name:
                entity = p.entity_name
            if p.name:
                project = p.name

        obj = cls(
            entity=entity,
            project=project,
            name=model.name,
            filters=expr_parsing.filters_to_expr(model.filters),
            groupby=[expr_parsing.to_frontend_name(k.name) for k in model.grouping],
            order=[OrderBy._from_model(s) for s in model.sort.keys],
        )
        obj._id = model.id
        return obj


@dataclass(config=dataclass_config, repr=False)
class Panel(Base):
    """A panel that displays a visualization in a panel grid.

    Attributes:
        layout (Layout): A `Layout` object.
    """

    layout: Layout = Field(default_factory=Layout, kw_only=True)

    _id: str = Field(
        default_factory=internal._generate_name, init=False, repr=False, kw_only=True
    )


@dataclass(config=dataclass_config, repr=False)
class PanelGrid(Block):
    """
    A grid that consists of runsets and panels. Add runsets and panels with
    `Runset` and `Panel` objects, respectively.

    Available panels include:
    `LinePlot`, `ScatterPlot`, `BarPlot`, `ScalarChart`, `CodeComparer`, `ParallelCoordinatesPlot`,
    `ParameterImportancePlot`, `RunComparer`, `MediaBrowser`, `MarkdownPanel`, `CustomChart`,
    `WeavePanel`, `WeavePanelSummaryTable`, `WeavePanelArtifactVersionedFile`.


    Attributes:
        runsets (LList["Runset"]): A list of one or more `Runset` objects.
        hide_run_sets (bool): Whether to hide the run sets of the panel grid for report viewers.
        panels (LList["PanelTypes"]): A list of one or more `Panel` objects.
        active_runset (int): The number of runs you want to display within a runset. By default, it is set to 0.
        custom_run_colors (dict): Key-value pairs where the key is the name of a
            run and the value is a color specified by a hexadecimal value.
    """

    runsets: LList["Runset"] = Field(default_factory=lambda: [Runset()])
    hide_run_sets: bool = False
    panels: LList["PanelTypes"] = Field(default_factory=list)
    active_runset: int = 0
    custom_run_colors: Dict[Union[RunId, RunsetGroup], Union[str, dict]] = Field(
        default_factory=dict
    )

    _open_viz: bool = Field(default_factory=lambda: True, init=False, repr=False)
    _panel_bank_sections: LList[Dict] = Field(
        default_factory=list, init=False, repr=False
    )

    def _to_model(self):
        return internal.PanelGrid(
            metadata=internal.PanelGridMetadata(
                run_sets=[rs._to_model() for rs in self.runsets],
                hide_run_sets=self.hide_run_sets,
                panel_bank_section_config=internal.PanelBankSectionConfig(
                    panels=[p._to_model() for p in self.panels],
                ),
                panels=internal.PanelGridMetadataPanels(
                    panel_bank_config=internal.PanelBankConfig(),
                    open_viz=self._open_viz,
                ),
                custom_run_colors=_to_color_dict(self.custom_run_colors, self.runsets),
            )
        )

    @classmethod
    def _from_model(cls, model: internal.PanelGrid):
        runsets = [Runset._from_model(rs) for rs in model.metadata.run_sets]
        obj = cls(
            runsets=runsets,
            hide_run_sets=model.metadata.hide_run_sets,
            panels=[
                _lookup_panel(p)
                for p in model.metadata.panel_bank_section_config.panels
            ],
            active_runset=model.metadata.open_run_set,
            custom_run_colors=_from_color_dict(
                model.metadata.custom_run_colors, runsets
            ),
            # _panel_bank_sections=model.metadata.panel_bank_config.sections,
        )
        obj._open_viz = model.metadata.open_viz
        return obj

    @validator("panels")
    def _resolve_collisions(cls, v):  # noqa: N805
        v2 = _resolve_collisions(v)
        return v2

    @validator("runsets")
    def _validate_list_not_empty(cls, v):  # noqa: N805
        if len(v) < 1:
            raise ValueError("must have at least one runset")
        return v


@dataclass(config=dataclass_config, repr=False)
class TableOfContents(Block):
    """
    A block that contains a list of sections and subsections using
    H1, H2, and H3 HTML blocks specified in a report.
    """

    def _to_model(self):
        return internal.TableOfContents()

    @classmethod
    def _from_model(cls, model: internal.TableOfContents):
        return cls()


@dataclass(config=dataclass_config, repr=False)
class Twitter(Block):
    """A block that displays a Twitter feed.

    Attributes:
        html (str): The HTML code to display the Twitter feed.
    """

    html: str

    def _to_model(self):
        return internal.Twitter(html=self.html)

    @classmethod
    def _from_model(cls, model: internal.Twitter):
        return cls(html=model.html)


@dataclass(config=dataclass_config, repr=False)
class WeaveBlock(Block):
    """
    INTERNAL: This class is not for public use.
    """


@dataclass(config=dataclass_config)
class WeaveBlockSummaryTable(Block):
    """
    A block that shows a W&B Table, pandas DataFrame,
    plot, or other value logged to W&B. The query takes the form of

    ```python
    project('entity', 'project').runs.summary['value']
    ```

    The term "Weave" in the API name does not refer to
    the W&B Weave toolkit used for tracking and evaluating LLM.

    Attributes:
        entity (str): The entity that owns or has the
            appropriate permissions to the project where the values are logged.
        project (str): The project where the value is logged in.
        table_name (str): The name of the table, DataFrame, plot, or value.
    """

    entity: str
    project: str
    table_name: str

    def _to_model(self):
        return internal.WeaveBlock(
            config={
                "panelConfig": {
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {"project": "project"},
                                },
                            },
                            "value": {
                                "type": "list",
                                "objectType": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                    "value": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {},
                                                },
                                            },
                                            "none",
                                        ],
                                    },
                                },
                            },
                        },
                        "fromOp": {
                            "name": "pick",
                            "inputs": {
                                "obj": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {"project": "project"},
                                            },
                                        },
                                        "value": {
                                            "type": "list",
                                            "objectType": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {"run": "run"},
                                                },
                                                "value": {
                                                    "type": "union",
                                                    "members": [
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "_wandb": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "runtime": "number"
                                                                    },
                                                                }
                                                            },
                                                        },
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "_step": "number",
                                                                "table": {
                                                                    "type": "file",
                                                                    "extension": "json",
                                                                    "wbObjectType": {
                                                                        "type": "table",
                                                                        "columnTypes": {},
                                                                    },
                                                                },
                                                                "_wandb": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "runtime": "number"
                                                                    },
                                                                },
                                                                "_runtime": "number",
                                                                "_timestamp": "number",
                                                            },
                                                        },
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {},
                                                        },
                                                    ],
                                                },
                                            },
                                        },
                                    },
                                    "fromOp": {
                                        "name": "run-summary",
                                        "inputs": {
                                            "run": {
                                                "nodeType": "output",
                                                "type": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "tagged",
                                                        "tag": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "entityName": "string",
                                                                "projectName": "string",
                                                            },
                                                        },
                                                        "value": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "project": "project"
                                                            },
                                                        },
                                                    },
                                                    "value": {
                                                        "type": "list",
                                                        "objectType": "run",
                                                    },
                                                },
                                                "fromOp": {
                                                    "name": "project-runs",
                                                    "inputs": {
                                                        "project": {
                                                            "nodeType": "output",
                                                            "type": {
                                                                "type": "tagged",
                                                                "tag": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "entityName": "string",
                                                                        "projectName": "string",
                                                                    },
                                                                },
                                                                "value": "project",
                                                            },
                                                            "fromOp": {
                                                                "name": "root-project",
                                                                "inputs": {
                                                                    "entityName": {
                                                                        "nodeType": "const",
                                                                        "type": "string",
                                                                        "val": self.entity,
                                                                    },
                                                                    "projectName": {
                                                                        "nodeType": "const",
                                                                        "type": "string",
                                                                        "val": self.project,
                                                                    },
                                                                },
                                                            },
                                                        }
                                                    },
                                                },
                                            }
                                        },
                                    },
                                },
                                "key": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": self.table_name,
                                },
                            },
                        },
                        "__userInput": True,
                    }
                }
            }
        )

    @classmethod
    def _from_model(cls, model: internal.WeaveBlock):
        inputs = internal._get_weave_block_inputs(model.config)
        entity = inputs["obj"]["fromOp"]["inputs"]["run"]["fromOp"]["inputs"][
            "project"
        ]["fromOp"]["inputs"]["entityName"]["val"]
        project = inputs["obj"]["fromOp"]["inputs"]["run"]["fromOp"]["inputs"][
            "project"
        ]["fromOp"]["inputs"]["projectName"]["val"]
        table_name = inputs["key"]["val"]
        return cls(entity=entity, project=project, table_name=table_name)


@dataclass(config=dataclass_config)
class WeaveBlockArtifactVersionedFile(Block):
    """
    A block that shows a versioned file logged to a W&B artifact. The query takes the form of

    ```python
    project('entity', 'project').artifactVersion('name', 'version').file('file-name')
    ```

    The term "Weave" in the API name does not refer to
    the W&B Weave toolkit used for tracking and evaluating LLM.

    Attributes:
        entity (str): The entity that owns or has the
            appropriate permissions to the project where the artifact is stored.
        project (str): The project where the artifact is stored.
        artifact (str): The name of the artifact to retrieve.
        version (str): The version of the artifact to retrieve.
        file (str): The name of the file stored in the artifact to retrieve.
    """

    # TODO: Replace with actual weave blocks when ready
    entity: str
    project: str
    artifact: str
    version: str
    file: str

    def _to_model(self):
        return internal.WeaveBlock(
            config={
                "panelConfig": {
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                        "artifactVersionAlias": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "file",
                                "extension": "json",
                                "wbObjectType": {"type": "table", "columnTypes": {}},
                            },
                        },
                        "fromOp": {
                            "name": "artifactVersion-file",
                            "inputs": {
                                "artifactVersion": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "artifactName": "string",
                                                    "artifactVersionAlias": "string",
                                                },
                                            },
                                        },
                                        "value": "artifactVersion",
                                    },
                                    "fromOp": {
                                        "name": "project-artifactVersion",
                                        "inputs": {
                                            "project": {
                                                "nodeType": "output",
                                                "type": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "entityName": "string",
                                                            "projectName": "string",
                                                        },
                                                    },
                                                    "value": "project",
                                                },
                                                "fromOp": {
                                                    "name": "root-project",
                                                    "inputs": {
                                                        "entityName": {
                                                            "nodeType": "const",
                                                            "type": "string",
                                                            "val": self.entity,
                                                        },
                                                        "projectName": {
                                                            "nodeType": "const",
                                                            "type": "string",
                                                            "val": self.project,
                                                        },
                                                    },
                                                },
                                            },
                                            "artifactName": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": self.artifact,
                                            },
                                            "artifactVersionAlias": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": self.version,
                                            },
                                        },
                                    },
                                },
                                "path": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": self.file,
                                },
                            },
                        },
                        "__userInput": True,
                    }
                }
            }
        )

    @classmethod
    def _from_model(cls, model: internal.WeaveBlock):
        inputs = internal._get_weave_block_inputs(model.config)
        entity = inputs["artifactVersion"]["fromOp"]["inputs"]["project"]["fromOp"][
            "inputs"
        ]["entityName"]["val"]
        project = inputs["artifactVersion"]["fromOp"]["inputs"]["project"]["fromOp"][
            "inputs"
        ]["projectName"]["val"]
        artifact = inputs["artifactVersion"]["fromOp"]["inputs"]["artifactName"]["val"]
        version = inputs["artifactVersion"]["fromOp"]["inputs"]["artifactVersionAlias"][
            "val"
        ]
        file = inputs["path"]["val"]
        return cls(
            entity=entity,
            project=project,
            artifact=artifact,
            version=version,
            file=file,
        )


@dataclass(config=dataclass_config)
class WeaveBlockArtifact(Block):
    """
    A block that shows an artifact logged to W&B. The query takes the form of

    ```python
    project('entity', 'project').artifact('artifact-name')
    ```

    The term "Weave" in the API name does not refer to
    the W&B Weave toolkit used for tracking and evaluating LLM.

    Attributes:
        entity (str): The entity that owns or has the appropriate
            permissions to the project where the artifact is stored.
        project (str): The project where the artifact is stored.
        artifact (str): The name of the artifact to retrieve.
        tab Literal["overview", "metadata", "usage", "files", "lineage"]: The
            tab to display in the artifact panel.
    """

    # TODO: Replace with actual weave blocks when ready
    entity: str
    project: str
    artifact: str
    tab: Literal["overview", "metadata", "usage", "files", "lineage"] = "overview"

    def _to_model(self):
        return internal.WeaveBlock(
            config={
                "panelConfig": {
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": "artifact",
                        },
                        "fromOp": {
                            "name": "project-artifact",
                            "inputs": {
                                "project": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string",
                                            },
                                        },
                                        "value": "project",
                                    },
                                    "fromOp": {
                                        "name": "root-project",
                                        "inputs": {
                                            "entityName": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": self.entity,
                                            },
                                            "projectName": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": self.project,
                                            },
                                        },
                                    },
                                },
                                "artifactName": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": self.artifact,
                                },
                            },
                        },
                        "__userInput": True,
                    },
                    "panelInputType": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifact",
                    },
                    "panelConfig": {
                        "tabConfigs": {"overview": {"selectedTab": self.tab}}
                    },
                }
            }
        )

    @classmethod
    def _from_model(cls, model: internal.WeaveBlock):
        inputs = internal._get_weave_block_inputs(model.config)
        entity = inputs["project"]["fromOp"]["inputs"]["entityName"]["val"]
        project = inputs["project"]["fromOp"]["inputs"]["projectName"]["val"]
        artifact = inputs["artifactName"]["val"]
        tab = model.config["panelConfig"]["panelConfig"]["tabConfigs"]["overview"].get(
            "selectedTab", "overview"
        )
        return cls(entity=entity, project=project, artifact=artifact, tab=tab)


defined_weave_blocks = [
    WeaveBlockSummaryTable,
    WeaveBlockArtifactVersionedFile,
    WeaveBlockArtifact,
]


BlockTypes = Union[
    H1,
    H2,
    H3,
    P,
    CodeBlock,
    MarkdownBlock,
    LatexBlock,
    Image,
    UnorderedList,
    OrderedList,
    CheckedList,
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
    WeaveBlockSummaryTable,
    WeaveBlockArtifactVersionedFile,
    WeaveBlockArtifact,
    UnknownBlock,
]


block_mapping = {
    internal.Paragraph: P,
    internal.CalloutBlock: CalloutBlock,
    internal.CodeBlock: CodeBlock,
    internal.Gallery: Gallery,
    internal.Heading: Heading,
    internal.HorizontalRule: HorizontalRule,
    internal.Image: Image,
    internal.LatexBlock: LatexBlock,
    internal.List: List,
    internal.MarkdownBlock: MarkdownBlock,
    internal.PanelGrid: PanelGrid,
    internal.TableOfContents: TableOfContents,
    internal.Video: Video,
    internal.BlockQuote: BlockQuote,
    internal.Spotify: Spotify,
    internal.Twitter: Twitter,
    internal.SoundCloud: SoundCloud,
    internal.WeaveBlock: WeaveBlock,
    internal.UnknownBlock: UnknownBlock,
}


@dataclass(config=dataclass_config, repr=False)
class GradientPoint(Base):
    """
    A point in a gradient.

    Attributes:
        color: The color of the point.
        offset: The position of the point in the gradient. The value should be between 0 and 100.
    """

    color: Annotated[str, internal.ColorStrConstraints]
    offset: Annotated[float, Ge(0), Le(100)] = 0

    def _to_model(self):
        return internal.GradientPoint(color=self.color, offset=self.offset)

    @classmethod
    def _from_model(cls, model: internal.GradientPoint):
        return cls(color=model.color, offset=model.offset)


@dataclass(config=dataclass_config, repr=False)
class LinePlot(Panel):
    """
    A panel object with 2D line plots.

    Attributes:
        title (Optional[str]): The text that appears at the top of the plot.
        x (Optional[MetricType]): The name of a metric logged to your W&B project that the
            report pulls information from. The metric specified is used for the x-axis.
        y (LList[MetricType]): One or more metrics logged to your W&B project that the report pulls
            information from. The metric specified is used for the y-axis.
        range_x (Tuple[float | `None`, float | `None`]): Tuple that specifies the range of the x-axis.
        range_y (Tuple[float | `None`, float | `None`]): Tuple that specifies the range of the y-axis.
        log_x (Optional[bool]): Plots the x-coordinates using a base-10 logarithmic scale.
        log_y (Optional[bool]): Plots the y-coordinates using a base-10 logarithmic scale.
        title_x (Optional[str]): The label of the x-axis.
        title_y (Optional[str]): The label of the y-axis.
        ignore_outliers (Optional[bool]): If set to `True`, do not plot outliers.
        groupby (Optional[str]): Group runs based on a metric logged to your W&B project that the
            report pulls information from.
        groupby_aggfunc (Optional[GroupAgg]): Aggregate runs with specified
            function. Options include "mean", "min", "max", "median", "sum", "samples", or `None`.
        groupby_rangefunc (Optional[GroupArea]):  Group runs based on a range. Options
            include "minmax", "stddev", "stderr", "none", "samples", or `None`.
        smoothing_factor (Optional[float]): The smoothing factor to apply to the
            smoothing type. Accepted values range between 0 and 1.
        smoothing_type Optional[SmoothingType]: Apply a filter based on the specified
            distribution. Options include "exponentialTimeWeighted", "exponential",
            "gaussian", "average", or "none".
        smoothing_show_original (Optional[bool]):   If set to `True`, show the original data.
        max_runs_to_show (Optional[int]): The maximum number of runs to show on the line plot.
        custom_expressions (Optional[LList[str]]): Custom expressions to apply to the data.
        plot_type Optional[LinePlotStyle]: The type of line plot to generate.
            Options include "line", "stacked-area", or "pct-area".
        font_size Optional[FontSize]: The size of the line plot's font.
            Options include "small", "medium", "large", "auto", or `None`.
        legend_position Optional[LegendPosition]: Where to place the legend.
            Options include "north", "south", "east", "west", or `None`.
        legend_template (Optional[str]): The template for the legend.
        aggregate (Optional[bool]): If set to `True`, aggregate the data.
        xaxis_expression (Optional[str]): The expression for the x-axis.
        legend_fields (Optional[LList[str]]): The fields to include in the legend.
    """

    title: Optional[str] = None
    x: Optional[MetricType] = "Step"
    y: LList[MetricType] = Field(default_factory=list)
    range_x: Range = Field(default_factory=lambda: (None, None))
    range_y: Range = Field(default_factory=lambda: (None, None))
    log_x: Optional[bool] = None
    log_y: Optional[bool] = None
    title_x: Optional[str] = None
    title_y: Optional[str] = None
    ignore_outliers: Optional[bool] = None
    groupby: Optional[Union[str, Config]] = None
    groupby_aggfunc: Optional[GroupAgg] = None
    groupby_rangefunc: Optional[GroupArea] = None
    smoothing_factor: Optional[float] = None
    smoothing_type: Optional[SmoothingType] = None
    smoothing_show_original: Optional[bool] = None
    max_runs_to_show: Optional[int] = None
    custom_expressions: Optional[LList[str]] = None
    plot_type: Optional[LinePlotStyle] = None
    font_size: Optional[FontSize] = None
    legend_position: Optional[LegendPosition] = None
    legend_template: Optional[str] = None
    aggregate: Optional[bool] = None
    xaxis_expression: Optional[str] = None
    xaxis_format: Optional[str] = None
    legend_fields: Optional[LList[str]] = None

    def _to_model(self):
        return internal.LinePlot(
            config=internal.LinePlotConfig(
                chart_title=self.title,
                x_axis=_metric_to_backend(self.x),
                metrics=[_metric_to_backend(name) for name in _listify(self.y)],
                x_axis_min=self.range_x[0],
                x_axis_max=self.range_x[1],
                y_axis_min=self.range_y[0],
                y_axis_max=self.range_y[1],
                x_log_scale=self.log_x,
                y_log_scale=self.log_y,
                x_axis_title=self.title_x,
                y_axis_title=self.title_y,
                ignore_outliers=self.ignore_outliers,
                group_by=_metric_to_backend_groupby(self.groupby),
                group_agg=self.groupby_aggfunc,
                group_area=self.groupby_rangefunc,
                smoothing_weight=self.smoothing_factor,
                smoothing_type=self.smoothing_type,
                show_original_after_smoothing=self.smoothing_show_original,
                limit=self.max_runs_to_show,
                expressions=self.custom_expressions,
                plot_type=self.plot_type,
                font_size=self.font_size,
                legend_position=self.legend_position,
                legend_template=self.legend_template,
                aggregate=True if self.groupby else self.aggregate,
                x_expression=self.xaxis_expression,
                x_axis_format=self.xaxis_format,
                legend_fields=self.legend_fields,
            ),
            id=self._id,
            layout=self.layout._to_model(),
        )

    @classmethod
    def _from_model(cls, model: internal.LinePlot):
        obj = cls(
            title=model.config.chart_title,
            x=_metric_to_frontend(model.config.x_axis),
            y=[_metric_to_frontend(name) for name in model.config.metrics],
            range_x=(model.config.x_axis_min, model.config.x_axis_max),
            range_y=(model.config.y_axis_min, model.config.y_axis_max),
            log_x=model.config.x_log_scale,
            log_y=model.config.y_log_scale,
            title_x=model.config.x_axis_title,
            title_y=model.config.y_axis_title,
            ignore_outliers=model.config.ignore_outliers,
            groupby=_metric_to_frontend_groupby(model.config.group_by),
            groupby_aggfunc=model.config.group_agg,
            groupby_rangefunc=model.config.group_area,
            smoothing_factor=model.config.smoothing_weight,
            smoothing_type=model.config.smoothing_type,
            smoothing_show_original=model.config.show_original_after_smoothing,
            max_runs_to_show=model.config.limit,
            custom_expressions=model.config.expressions,
            plot_type=model.config.plot_type,
            font_size=model.config.font_size,
            legend_position=model.config.legend_position,
            legend_template=model.config.legend_template,
            aggregate=model.config.aggregate,
            xaxis_expression=model.config.x_expression,
            xaxis_format=model.config.x_axis_format,
            layout=Layout._from_model(model.layout),
            legend_fields=model.config.legend_fields,
        )
        obj._id = model.id
        return obj


@dataclass(config=dataclass_config, repr=False)
class ScatterPlot(Panel):
    """
    A panel object that shows a 2D or 3D scatter plot.

    Arguments:
        title (Optional[str]): The text that appears at the top of the plot.
        x Optional[SummaryOrConfigOnlyMetric]: The name of a metric logged to your W&B project that the
            report pulls information from. The metric specified is used for the x-axis.
        y Optional[SummaryOrConfigOnlyMetric]:  One or more metrics logged to your W&B project that the report pulls
            information from. Metrics specified are plotted within the y-axis.
        z Optional[SummaryOrConfigOnlyMetric]:
        range_x (Tuple[float | `None`, float | `None`]): Tuple that specifies the range of the x-axis.
        range_y (Tuple[float | `None`, float | `None`]): Tuple that specifies the range of the y-axis.
        range_z (Tuple[float | `None`, float | `None`]): Tuple that specifies the range of the z-axis.
        log_x (Optional[bool]): Plots the x-coordinates using a base-10 logarithmic scale.
        log_y (Optional[bool]): Plots the y-coordinates using a base-10 logarithmic scale.
        log_z (Optional[bool]): Plots the z-coordinates using a base-10 logarithmic scale.
        running_ymin (Optional[bool]):  Apply a moving average or rolling mean.
        running_ymax (Optional[bool]): Apply a moving average or rolling mean.
        running_ymean (Optional[bool]): Apply a moving average or rolling mean.
        legend_template (Optional[str]):  A string that specifies the format of the legend.
        gradient (Optional[LList[GradientPoint]]):  A list of gradient points that specify the color gradient of the plot.
        font_size (Optional[FontSize]): The size of the line plot's font.
            Options include "small", "medium", "large", "auto", or `None`.
        regression (Optional[bool]): If `True`, a regression line is plotted on the scatter plot.
    """

    title: Optional[str] = None
    x: Optional[SummaryOrConfigOnlyMetric] = None
    y: Optional[SummaryOrConfigOnlyMetric] = None
    z: Optional[SummaryOrConfigOnlyMetric] = None
    range_x: Range = Field(default_factory=lambda: (None, None))
    range_y: Range = Field(default_factory=lambda: (None, None))
    range_z: Range = Field(default_factory=lambda: (None, None))
    log_x: Optional[bool] = None
    log_y: Optional[bool] = None
    log_z: Optional[bool] = None
    running_ymin: Optional[bool] = None
    running_ymax: Optional[bool] = None
    running_ymean: Optional[bool] = None
    legend_template: Optional[str] = None
    gradient: Optional[LList[GradientPoint]] = None
    font_size: Optional[FontSize] = None
    regression: Optional[bool] = None

    def _to_model(self):
        custom_gradient = self.gradient
        if custom_gradient is not None:
            custom_gradient = [cgp._to_model() for cgp in self.gradient]

        return internal.ScatterPlot(
            config=internal.ScatterPlotConfig(
                chart_title=self.title,
                x_axis=_metric_to_backend_pc(self.x),
                y_axis=_metric_to_backend_pc(self.y),
                z_axis=_metric_to_backend_pc(self.z),
                x_axis_min=self.range_x[0],
                x_axis_max=self.range_x[1],
                y_axis_min=self.range_y[0],
                y_axis_max=self.range_y[1],
                z_axis_min=self.range_z[0],
                z_axis_max=self.range_z[1],
                x_axis_log_scale=self.log_x,
                y_axis_log_scale=self.log_y,
                z_axis_log_scale=self.log_z,
                show_min_y_axis_line=self.running_ymin,
                show_max_y_axis_line=self.running_ymax,
                show_avg_y_axis_line=self.running_ymean,
                legend_template=self.legend_template,
                custom_gradient=custom_gradient,
                font_size=self.font_size,
                show_linear_regression=self.regression,
            ),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        gradient = model.config.custom_gradient
        if gradient is not None:
            gradient = [GradientPoint._from_model(cgp) for cgp in gradient]

        obj = cls(
            title=model.config.chart_title,
            x=_metric_to_frontend_pc(model.config.x_axis),
            y=_metric_to_frontend_pc(model.config.y_axis),
            z=_metric_to_frontend_pc(model.config.z_axis),
            range_x=(model.config.x_axis_min, model.config.x_axis_max),
            range_y=(model.config.y_axis_min, model.config.y_axis_max),
            range_z=(model.config.z_axis_min, model.config.z_axis_max),
            log_x=model.config.x_axis_log_scale,
            log_y=model.config.y_axis_log_scale,
            log_z=model.config.z_axis_log_scale,
            running_ymin=model.config.show_min_y_axis_line,
            running_ymax=model.config.show_max_y_axis_line,
            running_ymean=model.config.show_avg_y_axis_line,
            legend_template=model.config.legend_template,
            gradient=gradient,
            font_size=model.config.font_size,
            regression=model.config.show_linear_regression,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id
        return obj


@dataclass(config=dataclass_config, repr=False)
class BarPlot(Panel):
    """
    A panel object that shows a 2D bar plot.

    Attributes:
        title (Optional[str]): The text that appears at the top of the plot.
        metrics (LList[MetricType]): orientation Literal["v", "h"]: The orientation of the bar plot.
            Set to either vertical ("v") or horizontal ("h"). Defaults to horizontal ("h").
        range_x (Tuple[float | None, float | None]): Tuple that specifies the range of the x-axis.
        title_x (Optional[str]): The label of the x-axis.
        title_y (Optional[str]): The label of the y-axis.
        groupby (Optional[str]): Group runs based on a metric logged to your W&B project that the
            report pulls information from.
        groupby_aggfunc (Optional[GroupAgg]): Aggregate runs with specified
            function. Options include "mean", "min", "max", "median", "sum", "samples", or `None`.
        groupby_rangefunc (Optional[GroupArea]):  Group runs based on a range. Options
            include "minmax", "stddev", "stderr", "none", "samples", or `None`.
        max_runs_to_show (Optional[int]): The maximum number of runs to show on the plot.
        max_bars_to_show (Optional[int]): The maximum number of bars to show on the bar plot.
        custom_expressions (Optional[LList[str]]): A list of custom expressions to be used in the bar plot.
        legend_template (Optional[str]): The template for the legend.
        font_size( Optional[FontSize]): The size of the line plot's font.
            Options include "small", "medium", "large", "auto", or `None`.
        line_titles (Optional[dict]): The titles of the lines. The keys are the line names and the values are the titles.
        line_colors (Optional[dict]): The colors of the lines. The keys are the line names and the values are the colors.
        aggregate (Optional[bool]): If set to `True`, aggregate the data.
    """

    title: Optional[str] = None
    metrics: LList[MetricType] = Field(default_factory=list)
    orientation: Literal["v", "h"] = "h"
    range_x: Range = Field(default_factory=lambda: (None, None))
    title_x: Optional[str] = None
    title_y: Optional[str] = None
    groupby: Optional[Union[str, Config]] = None
    groupby_aggfunc: Optional[GroupAgg] = None
    groupby_rangefunc: Optional[GroupArea] = None
    max_runs_to_show: Optional[int] = None
    max_bars_to_show: Optional[int] = None
    custom_expressions: Optional[LList[str]] = None
    legend_template: Optional[str] = None
    font_size: Optional[FontSize] = None
    line_titles: Optional[dict] = None
    line_colors: Optional[dict] = None
    aggregate: Optional[bool] = None

    def _to_model(self):
        return internal.BarPlot(
            config=internal.BarPlotConfig(
                chart_title=self.title,
                metrics=[_metric_to_backend(name) for name in _listify(self.metrics)],
                vertical=self.orientation == "v",
                x_axis_min=self.range_x[0],
                x_axis_max=self.range_x[1],
                x_axis_title=self.title_x,
                y_axis_title=self.title_y,
                group_by=_metric_to_backend_groupby(self.groupby),
                group_agg=self.groupby_aggfunc,
                group_area=self.groupby_rangefunc,
                limit=self.max_runs_to_show,
                bar_limit=self.max_bars_to_show,
                expressions=self.custom_expressions,
                legend_template=self.legend_template,
                font_size=self.font_size,
                override_series_titles=self.line_titles,
                override_colors=self.line_colors,
                aggregate=True if self.groupby else self.aggregate,
            ),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        obj = cls(
            title=model.config.chart_title,
            metrics=[_metric_to_frontend(name) for name in model.config.metrics],
            orientation="v" if model.config.vertical else "h",
            range_x=(model.config.x_axis_min, model.config.x_axis_max),
            title_x=model.config.x_axis_title,
            title_y=model.config.y_axis_title,
            groupby=_metric_to_frontend_groupby(model.config.group_by),
            groupby_aggfunc=model.config.group_agg,
            groupby_rangefunc=model.config.group_area,
            max_runs_to_show=model.config.limit,
            max_bars_to_show=model.config.bar_limit,
            custom_expressions=model.config.expressions,
            legend_template=model.config.legend_template,
            font_size=model.config.font_size,
            line_titles=model.config.override_series_titles,
            line_colors=model.config.override_colors,
            aggregate=model.config.aggregate,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id
        return obj


@dataclass(config=dataclass_config, repr=False)
class ScalarChart(Panel):
    """
    A panel object that shows a scalar chart.

    Attributes:
        title (Optional[str]): The text that appears at the top of the plot.
        metric (MetricType): The name of a metric logged to your W&B project that the
            report pulls information from.
        groupby_aggfunc (Optional[GroupAgg]): Aggregate runs with specified
            function. Options include "mean", "min", "max", "median", "sum", "samples", or `None`.
        groupby_rangefunc (Optional[GroupArea]):  Group runs based on a range. Options
            include "minmax", "stddev", "stderr", "none", "samples", or `None`.
        custom_expressions (Optional[LList[str]]): A list of custom expressions to be used in the scalar chart.
        legend_template (Optional[str]): The template for the legend.
        font_size Optional[FontSize]: The size of the line plot's font.
            Options include "small", "medium", "large", "auto", or `None`.

    """

    title: Optional[str] = None
    metric: MetricType = ""
    groupby_aggfunc: Optional[GroupAgg] = None
    groupby_rangefunc: Optional[GroupArea] = None
    custom_expressions: Optional[LList[str]] = None
    legend_template: Optional[str] = None
    font_size: Optional[FontSize] = None

    def _to_model(self):
        return internal.ScalarChart(
            config=internal.ScalarChartConfig(
                chart_title=self.title,
                metrics=[_metric_to_backend(self.metric)],
                group_agg=self.groupby_aggfunc,
                group_area=self.groupby_rangefunc,
                expressions=self.custom_expressions,
                legend_template=self.legend_template,
                font_size=self.font_size,
            ),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        obj = cls(
            title=model.config.chart_title,
            metric=_metric_to_frontend(model.config.metrics[0]),
            groupby_aggfunc=model.config.group_agg,
            groupby_rangefunc=model.config.group_area,
            custom_expressions=model.config.expressions,
            legend_template=model.config.legend_template,
            font_size=model.config.font_size,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id
        return obj


@dataclass(config=dataclass_config, repr=False)
class CodeComparer(Panel):
    """
    A panel object that compares the code between two different runs.

    Attributes:
        diff (Literal['split', 'unified']): How to display code differences.
            Options include "split" and "unified".
    """

    diff: CodeCompareDiff = "split"

    def _to_model(self):
        return internal.CodeComparer(
            config=internal.CodeComparerConfig(diff=self.diff),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        obj = cls(
            diff=model.config.diff,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id
        return obj


@dataclass(config=dataclass_config, repr=False)
class ParallelCoordinatesPlotColumn(Base):
    """
    A column within a parallel coordinates plot.  The order of `metric`s specified
    determine the order of the parallel axis (x-axis) in the parallel coordinates plot.

    Attributes:
        metric (str | Config | SummaryMetric): The name of the
            metric logged to your W&B project that the report pulls information from.
        display_name (Optional[str]): The name of the metric
        inverted (Optional[bool]): Whether to invert the metric.
        log (Optional[bool]): Whether to apply a log transformation to the metric.
    """

    metric: SummaryOrConfigOnlyMetric
    display_name: Optional[str] = None
    inverted: Optional[bool] = None
    log: Optional[bool] = None

    def _to_model(self):
        return internal.Column(
            accessor=_metric_to_backend_pc(self.metric),
            display_name=self.display_name,
            inverted=self.inverted,
            log=self.log,
        )

    @classmethod
    def _from_model(cls, model: internal.Column):
        obj = cls(
            metric=_metric_to_frontend_pc(model.accessor),
            display_name=model.display_name,
            inverted=model.inverted,
            log=model.log,
        )
        return obj


@dataclass(config=dataclass_config, repr=False)
class ParallelCoordinatesPlot(Panel):
    """
    A panel object that shows a parallel coordinates plot.

    Attributes:
        columns (LList[ParallelCoordinatesPlotColumn]): A list of one
            or more `ParallelCoordinatesPlotColumn` objects.
        title (Optional[str]): The text that appears at the top of the plot.
        gradient (Optional[LList[GradientPoint]]): A list of gradient points.
        font_size (Optional[FontSize]): The size of the line plot's font.
            Options include "small", "medium", "large", "auto", or `None`.
    """

    columns: LList[ParallelCoordinatesPlotColumn] = Field(default_factory=list)
    title: Optional[str] = None
    gradient: Optional[LList[GradientPoint]] = None
    font_size: Optional[FontSize] = None

    def _to_model(self):
        gradient = self.gradient
        if gradient is not None:
            gradient = [x._to_model() for x in self.gradient]

        return internal.ParallelCoordinatesPlot(
            config=internal.ParallelCoordinatesPlotConfig(
                chart_title=self.title,
                columns=[c._to_model() for c in self.columns],
                custom_gradient=gradient,
                font_size=self.font_size,
            ),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        gradient = model.config.custom_gradient
        if gradient is not None:
            gradient = [GradientPoint._from_model(x) for x in gradient]

        obj = cls(
            columns=[
                ParallelCoordinatesPlotColumn._from_model(c)
                for c in model.config.columns
            ],
            title=model.config.chart_title,
            gradient=gradient,
            font_size=model.config.font_size,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id
        return obj


@dataclass(config=dataclass_config, repr=False)
class ParameterImportancePlot(Panel):
    """
    A panel that shows how important each hyperparameter
    is in predicting the chosen metric.

    Attributes:
        with_respect_to (str): The metric you want to compare the
            parameter importance against. Common metrics might include the loss, accuracy,
            and so forth. The metric you specify must be logged within the project
            that the report pulls information from.
    """

    with_respect_to: str = ""

    def _to_model(self):
        return internal.ParameterImportancePlot(
            config=internal.ParameterImportancePlotConfig(
                target_key=self.with_respect_to
            ),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        obj = cls(
            with_respect_to=model.config.target_key,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id

        return obj


@dataclass(config=dataclass_config, repr=False)
class RunComparer(Panel):
    """
    A panel that compares metrics across different runs from
    the project the report pulls information from.

    Attributes:
        diff_only (Optional[Literal["split", `True`]]): Display only the
            difference across runs in a project. You can toggle this feature on and off in the W&B Report UI.
    """

    diff_only: Optional[Literal["split", True]] = None

    def _to_model(self):
        return internal.RunComparer(
            config=internal.RunComparerConfig(diff_only=self.diff_only),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        obj = cls(
            diff_only=model.config.diff_only,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id

        return obj


@dataclass(config=dataclass_config, repr=False)
class MediaBrowser(Panel):
    """
    A panel that displays media files in a grid layout.

    Attributes:
        title (Optional[str]): The title of the panel.
        num_columns (Optional[int]): The number of columns in the grid.
        media_keys (LList[str]): A list of media keys that correspond to the media files.
    """

    title: Optional[str] = None
    num_columns: Optional[int] = None
    media_keys: LList[str] = Field(default_factory=list)

    def _to_model(self):
        return internal.MediaBrowser(
            config=internal.MediaBrowserConfig(
                chart_title=self.title,
                column_count=self.num_columns,
                media_keys=self.media_keys,
            ),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.MediaBrowser):
        obj = cls(
            title=model.config.chart_title,
            num_columns=model.config.column_count,
            media_keys=model.config.media_keys,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id

        return obj


@dataclass(config=dataclass_config, repr=False)
class MarkdownPanel(Panel):
    """
    A panel that renders markdown.

    Attributes:
        markdown (str): The text you want to appear in the markdown panel.
    """

    markdown: str = ""

    def _to_model(self):
        return internal.MarkdownPanel(
            config=internal.MarkdownPanelConfig(value=self.markdown),
            layout=self.layout._to_model(),
            id=self._id,
        )

    @classmethod
    def _from_model(cls, model: internal.ScatterPlot):
        obj = cls(
            markdown=model.config.value,
            layout=Layout._from_model(model.layout),
        )
        obj._id = model.id

        return obj


@dataclass(config=dataclass_config, repr=False)
class CustomChart(Panel):
    """
    A panel that shows a custom chart. The chart is defined by a weave query.

    Attributes:
        query (dict): The query that defines the custom chart. The key is the name of the field, and the value is the query.
        chart_name (str): The title of the custom chart.
        chart_fields (dict): Key-value pairs that define the axis of the
            plot. Where the key is the label, and the value is the metric.
        chart_strings (dict): Key-value pairs that define the strings in the chart.

    """

    # Custom chart configs should look exactly like they do in the UI.  Please check the query carefully!
    query: dict = Field(default_factory=dict)
    chart_name: str = Field(default_factory=str)
    chart_fields: dict = Field(default_factory=dict)
    chart_strings: dict = Field(default_factory=dict)

    @classmethod
    def from_table(
        cls, table_name: str, chart_fields: dict = None, chart_strings: dict = None
    ):
        """
        Create a custom chart from a table.

        Arguments:
            table_name (str): The name of the table.
            chart_fields (dict): The fields to display in the chart.
            chart_strings (dict): The strings to display in the chart.
        """
        return cls(
            query={"summaryTable": {"tableKey": table_name}},
            chart_fields=chart_fields,
            chart_strings=chart_strings,
        )

    def _to_model(self):
        def dict_to_fields(d):
            fields = []
            for k, v in d.items():
                if k in ("runSets", "limit"):
                    continue
                if isinstance(v, dict) and len(v) > 0:
                    field = internal.QueryField(
                        name=k, args=dict_to_fields(v), fields=[]
                    )
                elif isinstance(v, dict) and len(v) == 0 or v is None:
                    field = internal.QueryField(name=k, fields=[])
                else:
                    field = internal.QueryField(name=k, value=v)
                fields.append(field)
            return fields

        d = self.query
        d.setdefault("id", None)
        d.setdefault("name", None)

        _query = [
            internal.QueryField(
                name="runSets",
                args=[
                    internal.QueryField(name="runSets", value=r"${runSets}"),
                    internal.QueryField(name="limit", value=500),
                ],
                fields=dict_to_fields(d),
            )
        ]
        user_query = internal.UserQuery(query_fields=_query)

        return internal.Vega2(
            config=internal.Vega2Config(
                user_query=user_query,
                panel_def_id=self.chart_name,
                field_settings=self.chart_fields,
                string_settings=self.chart_strings,
            ),
            layout=self.layout._to_model(),
        )

    @classmethod
    def _from_model(cls, model: internal.Vega2):
        def fields_to_dict(fields):
            d = {}
            for field in fields:
                if field.args:
                    for arg in field.args:
                        d[arg.name] = arg.value

                if field.fields:
                    for subfield in field.fields:
                        if subfield.args is not None:
                            d[subfield.name] = fields_to_dict(subfield.args)
                        else:
                            d[subfield.name] = subfield.value

                d[field.name] = field.value

            return d

        query = fields_to_dict(model.config.user_query.query_fields)

        return cls(
            query=query,
            chart_name=model.config.panel_def_id,
            chart_fields=model.config.field_settings,
            chart_strings=model.config.string_settings,
            layout=Layout._from_model(model.layout),
        )


@dataclass(config=ConfigDict(validate_assignment=True, extra="forbid", slots=True))
class UnknownPanel(Base):
    """
    INTERNAL: This class is not for public use.
    """

    def __repr__(self) -> str:
        class_name = self.__class__.__name__
        attributes = ", ".join(
            f"{key}={value!r}" for key, value in self.__dict__.items()
        )
        return f"{class_name}({attributes})"

    def _to_model(self):
        d = self.__dict__
        print(d)
        return internal.UnknownPanel.model_validate(d)

    @classmethod
    def _from_model(cls, model: internal.UnknownPanel):
        d = model.model_dump()
        return cls(**d)


@dataclass(config=ConfigDict(validate_assignment=True, extra="forbid", slots=True))
class WeavePanel(Panel):
    """
    An empty query panel that can be used to display custom content using queries.

    The term "Weave" in the API name does not refer to
    the W&B Weave toolkit used for tracking and evaluating LLM.
    """

    config: dict = Field(default_factory=dict)

    def _to_model(self):
        return internal.WeavePanel(config=self.config, layout=self.layout._to_model())

    @classmethod
    def _from_model(cls, model: internal.WeavePanel):
        return cls(config=model.config)


@dataclass(config=dataclass_config)
class WeavePanelSummaryTable(Panel):
    """
    A panel that shows a W&B Table, pandas DataFrame,
    plot, or other value logged to W&B. The query takes the form of

    ```python
    runs.summary['value']
    ```

    The term "Weave" in the API name does not refer to
    the W&B Weave toolkit used for tracking and evaluating LLM.

    Attributes:
        table_name (str): The name of the table, DataFrame, plot, or value.

    """

    # TODO: Replace with actual weave panels when ready
    table_name: str = Field(..., kw_only=True)

    def _to_model(self):
        return internal.WeavePanel(
            config={
                "panel2Config": {
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "filter": "string",
                                        "order": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "list",
                                "objectType": {
                                    "type": "tagged",
                                    "tag": {
                                        "type": "typedDict",
                                        "propertyTypes": {"run": "run"},
                                    },
                                    "value": {
                                        "type": "union",
                                        "members": [
                                            {
                                                "type": "file",
                                                "extension": "json",
                                                "wbObjectType": {
                                                    "type": "table",
                                                    "columnTypes": {},
                                                },
                                            },
                                            "none",
                                        ],
                                    },
                                },
                                "maxLength": 50,
                            },
                        },
                        "fromOp": {
                            "name": "pick",
                            "inputs": {
                                "obj": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "filter": "string",
                                                    "order": "string",
                                                },
                                            },
                                        },
                                        "value": {
                                            "type": "list",
                                            "objectType": {
                                                "type": "tagged",
                                                "tag": {
                                                    "type": "typedDict",
                                                    "propertyTypes": {"run": "run"},
                                                },
                                                "value": {
                                                    "type": "union",
                                                    "members": [
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "_wandb": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "runtime": "number"
                                                                    },
                                                                }
                                                            },
                                                        },
                                                        {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "_step": "number",
                                                                "table": {
                                                                    "type": "file",
                                                                    "extension": "json",
                                                                    "wbObjectType": {
                                                                        "type": "table",
                                                                        "columnTypes": {},
                                                                    },
                                                                },
                                                                "_wandb": {
                                                                    "type": "typedDict",
                                                                    "propertyTypes": {
                                                                        "runtime": "number"
                                                                    },
                                                                },
                                                                "_runtime": "number",
                                                                "_timestamp": "number",
                                                            },
                                                        },
                                                    ],
                                                },
                                            },
                                            "maxLength": 50,
                                        },
                                    },
                                    "fromOp": {
                                        "name": "run-summary",
                                        "inputs": {
                                            "run": {
                                                "nodeType": "var",
                                                "type": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "tagged",
                                                        "tag": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "entityName": "string",
                                                                "projectName": "string",
                                                            },
                                                        },
                                                        "value": {
                                                            "type": "typedDict",
                                                            "propertyTypes": {
                                                                "project": "project",
                                                                "filter": "string",
                                                                "order": "string",
                                                            },
                                                        },
                                                    },
                                                    "value": {
                                                        "type": "list",
                                                        "objectType": "run",
                                                        "maxLength": 50,
                                                    },
                                                },
                                                "varName": "runs",
                                            }
                                        },
                                    },
                                },
                                "key": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": self.table_name,
                                },
                            },
                        },
                        "__userInput": True,
                    }
                }
            },
            layout=self.layout._to_model(),
        )

    @classmethod
    def _from_model(cls, model: internal.WeavePanel):
        inputs = internal._get_weave_panel_inputs(model.config)
        table_name = inputs["key"]["val"]
        return cls(table_name=table_name)


@dataclass(config=dataclass_config)
class WeavePanelArtifactVersionedFile(Panel):
    """
    A panel that shows a versioned file logged to a W&B artifact.

    ```python
    project('entity', 'project').artifactVersion('name', 'version').file('file-name')
    ```

    The term "Weave" in the API name does not refer to
    the W&B Weave toolkit used for tracking and evaluating LLM.

    Attributes:
        artifact (str): The name of the artifact to retrieve.
        version (str): The version of the artifact to retrieve.
        file (str): The name of the file stored in the artifact to retrieve.
    """

    # TODO: Replace with actual weave panels when ready
    artifact: str = Field(..., kw_only=True)
    version: str = Field(..., kw_only=True)
    file: str = Field(..., kw_only=True)

    def _to_model(self):
        return internal.WeavePanel(
            config={
                "panel2Config": {
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                        "artifactVersionAlias": "string",
                                    },
                                },
                            },
                            "value": {
                                "type": "file",
                                "extension": "json",
                                "wbObjectType": {"type": "table", "columnTypes": {}},
                            },
                        },
                        "fromOp": {
                            "name": "artifactVersion-file",
                            "inputs": {
                                "artifactVersion": {
                                    "nodeType": "output",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "tagged",
                                            "tag": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "entityName": "string",
                                                    "projectName": "string",
                                                },
                                            },
                                            "value": {
                                                "type": "typedDict",
                                                "propertyTypes": {
                                                    "project": "project",
                                                    "artifactName": "string",
                                                    "artifactVersionAlias": "string",
                                                },
                                            },
                                        },
                                        "value": "artifactVersion",
                                    },
                                    "fromOp": {
                                        "name": "project-artifactVersion",
                                        "inputs": {
                                            "project": {
                                                "nodeType": "var",
                                                "type": {
                                                    "type": "tagged",
                                                    "tag": {
                                                        "type": "typedDict",
                                                        "propertyTypes": {
                                                            "entityName": "string",
                                                            "projectName": "string",
                                                        },
                                                    },
                                                    "value": "project",
                                                },
                                                "varName": "project",
                                            },
                                            "artifactName": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": self.artifact,
                                            },
                                            "artifactVersionAlias": {
                                                "nodeType": "const",
                                                "type": "string",
                                                "val": self.version,
                                            },
                                        },
                                    },
                                },
                                "path": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": self.file,
                                },
                            },
                        },
                        "__userInput": True,
                    }
                }
            },
            layout=self.layout._to_model(),
        )

    @classmethod
    def _from_model(cls, model: internal.WeavePanel):
        inputs = internal._get_weave_panel_inputs(model.config)
        artifact = inputs["artifactVersion"]["fromOp"]["inputs"]["artifactName"]["val"]
        version = inputs["artifactVersion"]["fromOp"]["inputs"]["artifactVersionAlias"][
            "val"
        ]
        file = inputs["path"]["val"]
        return cls(artifact=artifact, version=version, file=file)


@dataclass(config=dataclass_config)
class WeavePanelArtifact(WeavePanel):
    """
    A panel that shows an artifact logged to W&B.

    The term "Weave" in the API name does not refer to
    the W&B Weave toolkit used for tracking and evaluating LLM.

    Attributes:
        artifact (str): The name of the artifact to retrieve.
        tab Literal["overview", "metadata", "usage", "files", "lineage"]: The tab to display in the artifact panel.
    """

    # TODO: Replace with actual weave panels when ready
    artifact: str = Field(...)
    tab: Literal["overview", "metadata", "usage", "files", "lineage"] = "overview"

    def _to_model(self):
        return internal.WeavePanel(
            config={
                "panel2Config": {
                    "exp": {
                        "nodeType": "output",
                        "type": {
                            "type": "tagged",
                            "tag": {
                                "type": "tagged",
                                "tag": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "entityName": "string",
                                        "projectName": "string",
                                    },
                                },
                                "value": {
                                    "type": "typedDict",
                                    "propertyTypes": {
                                        "project": "project",
                                        "artifactName": "string",
                                    },
                                },
                            },
                            "value": "artifact",
                        },
                        "fromOp": {
                            "name": "project-artifact",
                            "inputs": {
                                "project": {
                                    "nodeType": "var",
                                    "type": {
                                        "type": "tagged",
                                        "tag": {
                                            "type": "typedDict",
                                            "propertyTypes": {
                                                "entityName": "string",
                                                "projectName": "string",
                                            },
                                        },
                                        "value": "project",
                                    },
                                    "varName": "project",
                                },
                                "artifactName": {
                                    "nodeType": "const",
                                    "type": "string",
                                    "val": self.artifact,
                                },
                            },
                        },
                        "__userInput": True,
                    },
                    "panelInputType": {
                        "type": "tagged",
                        "tag": {
                            "type": "tagged",
                            "tag": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "entityName": "string",
                                    "projectName": "string",
                                },
                            },
                            "value": {
                                "type": "typedDict",
                                "propertyTypes": {
                                    "project": "project",
                                    "artifactName": "string",
                                },
                            },
                        },
                        "value": "artifact",
                    },
                    "panelConfig": {
                        "tabConfigs": {"overview": {"selectedTab": self.tab}}
                    },
                }
            },
            layout=self.layout._to_model(),
        )

    @classmethod
    def _from_model(cls, model: internal.WeavePanel):
        inputs = internal._get_weave_panel_inputs(model.config)
        artifact = inputs["artifactName"]["val"]
        tab = model.config["panel2Config"]["panelConfig"]["tabConfigs"]["overview"].get(
            "selectedTab", "overview"
        )
        return cls(artifact=artifact, tab=tab)


@dataclass(config=dataclass_config, repr=False)
class Report(Base):
    """
    An object that represents a W&B Report. Use the returned object's `blocks` attribute to customize your report.
    Report objects do not automatically save. Use the `save()` method to persists changes.

    Attributes:
        project (str): The name of the W&B project you want to load in.
            The project specified appears in the report's URL.
        entity (str): The W&B entity that owns the report.
            The entity appears in the report's URL.
        title (str): The title of the report. The title
            appears at the top of the report as an H1 heading.
        description (str): A description of the report.
            The description appears underneath the report's title.
        blocks (LList[BlockTypes]): A list of one or more HTML tags,
            plots, grids, runsets, and more.
        width (Literal['readable', 'fixed', 'fluid']): The width of the report. Options include 'readable', 'fixed', 'fluid'.
    """

    project: str
    entity: str = Field(default_factory=lambda: _get_api().default_entity)
    title: str = Field("Untitled Report", max_length=128)
    description: str = ""
    blocks: LList[BlockTypes] = Field(default_factory=list)
    width: ReportWidth = "readable"

    id: str = Field(default_factory=lambda: "", init=False, repr=False, kw_only=True)
    _discussion_threads: list = Field(default_factory=list, init=False, repr=False)
    _panel_settings: dict = Field(default_factory=dict, init=False, repr=False)
    _authors: LList[Dict] = Field(default_factory=list, init=False, repr=False)
    _created_at: Optional[datetime] = Field(
        default_factory=lambda: None, init=False, repr=False
    )
    _updated_at: Optional[datetime] = Field(
        default_factory=lambda: None, init=False, repr=False
    )

    def _to_model(self):
        blocks = self.blocks
        if len(blocks) > 0 and blocks[0] != P():
            blocks = [P()] + blocks

        if len(blocks) > 0 and blocks[-1] != P():
            blocks = blocks + [P()]

        if not blocks:
            blocks = [P(), P()]

        return internal.ReportViewspec(
            display_name=self.title,
            description=self.description,
            project=internal.Project(name=self.project, entity_name=self.entity),
            id=self.id,
            created_at=self._created_at,
            updated_at=self._updated_at,
            spec=internal.Spec(
                panel_settings=self._panel_settings,
                blocks=[b._to_model() for b in blocks],
                width=self.width,
                authors=self._authors,
                discussion_threads=self._discussion_threads,
            ),
        )

    @classmethod
    def _from_model(cls, model: internal.ReportViewspec):
        blocks = model.spec.blocks

        if blocks[0] == internal.Paragraph():
            blocks = blocks[1:]

        if blocks[-1] == internal.Paragraph():
            blocks = blocks[:-1]

        obj = cls(
            title=model.display_name,
            description=model.description,
            entity=model.project.entity_name,
            project=model.project.name,
            blocks=[_lookup(b) for b in blocks],
        )
        obj.id = model.id
        obj._discussion_threads = model.spec.discussion_threads
        obj._panel_settings = model.spec.panel_settings
        obj._authors = model.spec.authors
        obj._created_at = model.created_at
        obj._updated_at = model.updated_at

        return obj

    @property
    def url(self):
        """
        The URL where the report is hosted. The report URL consists of
        `https://wandb.ai/{entity}/{project_name}/reports/`. Where `{entity}`
        and `{project_name}` consists of the entity that the report belongs
        to and the name of the project, respectively.
        """
        if self.id == "":
            raise AttributeError("save report or explicitly pass `id` to get a url")

        base = urlparse(_get_api().client.app_url)

        title = self.title.replace(" ", "-")

        scheme = base.scheme
        netloc = base.netloc
        path = os.path.join(self.entity, self.project, "reports", f"{title}--{self.id}")
        params = ""
        query = ""
        fragment = ""

        return urlunparse((scheme, netloc, path, params, query, fragment))

    def save(self, draft: bool = False, clone: bool = False):
        """Persists changes made to a report object."""
        model = self._to_model()

        # create project if not exists
        projects = _get_api().projects(self.entity)
        is_new_project = True
        for p in projects:
            if p.name == self.project:
                is_new_project = False
                break

        if is_new_project:
            _get_api().create_project(self.project, self.entity)

        r = _get_api().client.execute(
            gql.upsert_view,
            variable_values={
                "id": None if clone or not model.id else model.id,
                "name": internal._generate_name()
                if clone or not model.name
                else model.name,
                "entityName": model.project.entity_name,
                "projectName": model.project.name,
                "description": model.description,
                "displayName": model.display_name,
                "type": "runs/draft" if draft else "runs",
                "spec": model.spec.model_dump_json(by_alias=True, exclude_none=True),
            },
        )

        viewspec = r["upsertView"]["view"]
        new_model = internal.ReportViewspec.model_validate(viewspec)
        self.id = new_model.id

        wandb.termlog(f"Saved report to: {self.url}")
        return self

    def delete(self) -> bool:
        """Delete this report from W&B.

        This will also delete any draft views that reference this report.

        Returns:
            bool: ``True`` if the delete operation was acknowledged as
            successful by the backend, ``False`` otherwise.
        """
        if self.id == "":
            raise AttributeError(
                "Cannot delete a report that has not been saved or does not have an id."
            )

        response = _get_api().client.execute(
            gql.delete_view,
            variable_values={
                "id": self.id,
                "deleteDrafts": True,
            },
        )

        result = response.get("deleteView", {})
        success = result.get("success", False)

        if success:
            wandb.termlog(f"Deleted report: {self.id}")
        else:
            wandb.termwarn(
                "Failed to delete report – backend returned unsuccessful status."
            )

        return success

    @classmethod
    def from_url(cls, url: str, *, as_model: bool = False):
        """
        Load in the report into current environment. Pass in the URL where the report is hosted.

        Arguments:
            url (str): The URL where the report is hosted.
            as_model (bool): If True, return the model object instead of the Report object.
                By default, set to `False`.
        """
        vs = _url_to_viewspec(url)
        model = internal.ReportViewspec.model_validate(vs)
        if as_model:
            return model
        return cls._from_model(model)

    def to_html(self, height: int = 1024, hidden: bool = False) -> str:
        """
        Generate HTML containing an iframe displaying this report. Commonly
        used to within a Python notebook.

        Arguments:
            height (int): Height of the iframe.
            hidden (bool): If True, hide the iframe. Default set to `False`.
        """
        try:
            url = self.url + "?jupyter=true"
            style = f"border:none;width:100%;height:{height}px;"
            prefix = ""
            if hidden:
                style += "display:none;"
                prefix = wandb.sdk.lib.ipython.toggle_button("report")
            return prefix + f"<iframe src={url!r} style={style!r}></iframe>"
        except AttributeError:
            wandb.termlog("HTML repr will be available after you save the report!")

    def _repr_html_(self) -> str:
        return self.to_html()


def _get_api():
    try:
        return wandb.Api()
    except wandb.errors.UsageError as e:
        raise Exception("not logged in to W&B, try `wandb login --relogin`") from e


def _url_to_viewspec(url):
    report_id = _url_to_report_id(url)
    r = _get_api().client.execute(
        gql.view_report, variable_values={"reportId": report_id}
    )
    viewspec = r["view"]

    # The spec field is a JSON string, we need to parse it, strip refs, and re-serialize
    if "spec" in viewspec and isinstance(viewspec["spec"], str):
        import json

        spec_dict = json.loads(viewspec["spec"])
        _strip_refs(spec_dict)
        viewspec["spec"] = json.dumps(spec_dict)

    # Also strip refs from other fields in viewspec
    _strip_refs(viewspec)

    return viewspec


def _strip_refs(obj):
    """
    Recursively remove ref objects from the viewspec in place.

    These are temporary values from the frontend that should not be persisted.
    This function modifies the input object in place.

    Args:
        obj: The object to process (dict, list, or any other type)
    """
    if isinstance(obj, dict):
        # Helper function to check if a value is a valid ref object
        def is_valid_ref(value):
            """Check if value is a ref object with viewID, type, and id properties"""
            if isinstance(value, dict):
                return (
                    "viewID" in value
                    and isinstance(value.get("viewID"), str)
                    and "type" in value
                    and isinstance(value.get("type"), str)
                    and "id" in value
                    and isinstance(value.get("id"), str)
                )
            elif isinstance(value, list):
                # For lists, check if all items are valid ref objects
                return all(is_valid_ref(item) for item in value) if value else False
            return False

        # Collect keys to remove (can't modify dict while iterating)
        keys_to_remove = []
        for key, value in obj.items():
            if (key == "ref" or key.endswith(("Ref", "Refs"))) and is_valid_ref(value):
                keys_to_remove.append(key)

        # Remove the collected keys
        for key in keys_to_remove:
            del obj[key]

        # Recursively process remaining values
        for value in obj.values():
            _strip_refs(value)

    elif isinstance(obj, list):
        # Process each item in the list
        for item in obj:
            _strip_refs(item)

    # For other types (strings, numbers, etc.), no action needed


def _url_to_report_id(url):
    parse_result = urlparse(url)
    path = parse_result.path

    _, entity, project, _, name = path.split("/")

    # Use rfind to find the last occurrence of '--'
    separator_position = name.rfind("--")
    if separator_position == -1:
        raise ValueError("Attempted to parse invalid View ID: no separator found")

    # Split at the last '--'
    # title = name[:separator_position]  # Not used, commenting out to fix ruff warning
    report_id = name[separator_position + 2 :]  # +2 to skip the '--'

    # Add correct base64 padding: calculate the number of '=' needed
    pad = (4 - (len(report_id) % 4)) % 4
    padded_report_id = report_id + ("=" * pad)
    try:
        # Validate the padded report ID by attempting to decode it
        decoded = base64.b64decode(padded_report_id)
    except Exception as e:
        raise ValueError("Attempted to parse invalid View ID") from e

    # Re-encode to standard base64 string (which will include proper padding)
    report_id = base64.b64encode(decoded).decode("utf-8")
    return report_id


def _lookup(block):
    cls = block_mapping.get(block.__class__, UnknownBlock)

    if cls is UnknownBlock:
        wandb.termwarn(f"Unknown block type: {block.__class__}")

    if cls is WeaveBlock:
        for cls in defined_weave_blocks:
            try:
                cls._from_model(block)
            except Exception:
                continue
            else:
                break

    return cls._from_model(block)


def _should_show_attr(k, v):
    if k.startswith("_"):
        return False
    if k == "id":
        return False
    if v is None:
        return False
    if isinstance(v, Iterable) and not isinstance(v, (str, bytes, bytearray)):
        return not all(x is None for x in v)
    # ignore the default layout
    if isinstance(v, Layout) and v.x == 0 and v.y == 0 and v.w == 8 and v.h == 6:
        return False
    return True


def _listify(x):
    if isinstance(x, Iterable):
        return list(x)
    return [x]


def _lookup_panel(panel):
    cls = panel_mapping.get(panel.__class__, UnknownPanel)

    if cls is UnknownPanel:
        wandb.termwarn(f"Unknown panel type: {panel.__class__}")

    if cls is WeavePanel:
        # TODO the more panels that get defined, the more of a need there is to either
        # sort the `defined_weave_panels` list by specificity or add additional logic
        # to select the proper panel.
        #
        # Currently, WeaveSummaryTablePanel, WeavePanelArtifactVersionedFile, and
        # WeavePanelArtifact have unique keys from inputs, so this logic still works.
        for weave_cls in defined_weave_panels:
            try:
                return weave_cls._from_model(panel)
            except Exception:
                continue

    return cls._from_model(panel)


def _load_spec_from_url(url, as_model=False):
    import json

    vs = _url_to_viewspec(url)
    spec = vs["spec"]
    if as_model:
        return internal.Spec.model_validate_json(spec)
    return json.loads(spec)


defined_weave_panels = [
    WeavePanelSummaryTable,
    WeavePanelArtifactVersionedFile,
    WeavePanelArtifact,
]

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
    CustomChart,
    WeavePanel,
    WeavePanelSummaryTable,
    WeavePanelArtifactVersionedFile,
    WeavePanelArtifact,
    UnknownPanel,
]

panel_mapping = {
    internal.LinePlot: LinePlot,
    internal.ScatterPlot: ScatterPlot,
    internal.BarPlot: BarPlot,
    internal.ScalarChart: ScalarChart,
    internal.CodeComparer: CodeComparer,
    internal.ParallelCoordinatesPlot: ParallelCoordinatesPlot,
    internal.ParameterImportancePlot: ParameterImportancePlot,
    internal.RunComparer: RunComparer,
    internal.Vega2: CustomChart,
    internal.MediaBrowser: MediaBrowser,
    internal.MarkdownPanel: MarkdownPanel,
    internal.WeavePanel: WeavePanel,
}


def _text_to_internal_children(text_field):
    text = text_field
    if text == []:
        text = ""
    # if isinstance(text, str):
    if not isinstance(text, list):
        text = [text]

    texts = []
    for x in text:
        t = None
        if isinstance(x, str):
            t = internal.Text(text=x)
        elif isinstance(x, TextWithInlineComments):
            t = internal.Text(text=x.text, inline_comments=x._inline_comments)
        elif isinstance(x, Link):
            txt = x.text
            if isinstance(txt, str):
                children = [internal.Text(text=txt)]
            elif isinstance(txt, TextWithInlineComments):
                children = [
                    internal.Text(text=txt.text, inline_comments=txt._inline_comments)
                ]
            t = internal.InlineLink(url=x.url, children=children)
        elif isinstance(x, InlineLatex):
            t = internal.InlineLatex(content=x.text)
        elif isinstance(x, InlineCode):
            t = internal.Text(text=x.text, inline_code=True)
        texts.append(t)
    if not all(isinstance(x, str) for x in texts):
        pass
    return texts


def _generate_thing(x):
    if isinstance(x, internal.Paragraph):
        return _internal_children_to_text(x.children)
    elif isinstance(x, internal.Text):
        if x.inline_code:
            return InlineCode(x.text)
        elif x.inline_comments:
            return TextWithInlineComments(
                text=x.text, _inline_comments=x.inline_comments
            )
        return x.text
    elif isinstance(x, internal.InlineLink):
        text_obj = x.children[0]
        if text_obj.inline_comments:
            text = TextWithInlineComments(
                text=text_obj.text, _inline_comments=text_obj.inline_comments
            )
        else:
            text = text_obj.text
        return Link(url=x.url, text=text)
    elif isinstance(x, internal.InlineLatex):
        return InlineLatex(text=x.content)


def _internal_children_to_text(children):
    pieces = []
    for x in children:
        t = _generate_thing(x)
        if isinstance(t, list):
            for x in t:
                pieces.append(x)
        else:
            pieces.append(t)

    if not pieces:
        return ""

    if len(pieces) == 1 and isinstance(pieces[0], str):
        return pieces[0]

    if len(pieces) == 3 and pieces[0] == "" and pieces[-1] == "":
        return pieces[1]

    if len(pieces) >= 3 and pieces[0] == "" and pieces[-1] == "":
        return pieces[1:-1]

    if all(x == "" for x in pieces):
        return ""

    return pieces


def _resolve_collisions(panels: LList[Panel], x_max: int = 24):
    for i, p1 in enumerate(panels):
        for p2 in panels[i + 1 :]:
            l1, l2 = p1.layout, p2.layout

            if _collides(p1, p2):
                x = l1.x + l1.w - l2.x
                y = l1.y + l1.h - l2.y

                if l2.x + l2.w + x <= x_max:
                    l2.x += x

                else:
                    l2.y += y
                    l2.x = 0
    return panels


def _collides(p1: Panel, p2: Panel) -> bool:
    l1, l2 = p1.layout, p2.layout

    if (
        (p1._id == p2._id)
        or (l1.x + l1.w <= l2.x)
        or (l1.x >= l2.w + l2.x)
        or (l1.y + l1.h <= l2.y)
        or (l1.y >= l2.y + l2.h)
    ):
        return False

    return True


def _metric_to_backend(x: Optional[MetricType]):
    if x is None:
        return x
    if isinstance(x, str):  # Same as Metric
        return expr_parsing.to_backend_name(x)
    if isinstance(x, Metric):
        name = x.name
        return expr_parsing.to_backend_name(name)
    if isinstance(x, Config):
        name, *rest = x.name.split(".")
        rest = "." + ".".join(rest) if rest else ""
        return f"config.{name}.value{rest}"
    if isinstance(x, SummaryMetric):
        name = x.name
        return f"summary_metrics.{name}"
    raise Exception("Unexpected metric type")


def _metric_to_frontend(x: str):
    if x is None:
        return x
    if x.startswith("config.") and ".value" in x:
        name = x.replace("config.", "").replace(".value", "")
        return Config(name)

    summary_metrics_keys = ["summary_metrics.", "summary."]
    for k in summary_metrics_keys:
        if x.startswith(k):
            name = x.replace(k, "")
            return SummaryMetric(name)

    name = expr_parsing.to_frontend_name(x)
    return Metric(name)


def _metric_to_backend_pc(x: Optional[SummaryOrConfigOnlyMetric]):
    if x is None:
        return x
    # Accept explicit run section prefix ("run.") or treat Metric instances as run metrics.
    if isinstance(x, str):
        # If the user explicitly specified a run attribute, e.g. "run.createdAt",
        # strip the prefix and map the name to its backend representation.
        if x.startswith("run."):
            name = x.split("run.", 1)[1]
            backend_name = expr_parsing.to_backend_name(name)
            return f"run:{backend_name}"
        # Otherwise, assume summary metric (legacy behaviour)
        name = x
        return f"summary:{name}"
    if isinstance(x, Metric):
        # Run-level metric – convert to backend name (handles FE ⇄ BE mapping, e.g. "CreatedTimestamp" → "createdAt")
        name = x.name
        backend_name = expr_parsing.to_backend_name(name)
        return f"run:{backend_name}"
    if isinstance(x, Config):
        name = x.name
        return f"c::{name}"
    if isinstance(x, SummaryMetric):
        name = x.name
        return f"summary:{name}"
    raise Exception("Unexpected metric type")


def _metric_to_frontend_pc(x: str):
    if x is None:
        return x
    if x.startswith("c::"):
        name = x.replace("c::", "")
        return Config(name)
    if x.startswith("summary:"):
        name = x.replace("summary:", "")
        return SummaryMetric(name)
    if x.startswith("run:"):
        name = x.replace("run:", "")
        backend_name = expr_parsing.to_frontend_name(name)
        return Metric(backend_name)

    name = expr_parsing.to_frontend_name(x)
    return Metric(name)


def _metric_to_backend_panel_grid(x: Optional[MetricType]):
    if isinstance(x, str):
        name, *rest = x.split(".")
        rest = "." + ".".join(rest) if rest else ""
        return f"config:{name}.value{rest}"
    return _metric_to_backend(x)


def _metric_to_frontend_panel_grid(x: str):
    if x.startswith("config:") and ".value" in x:
        name = x.replace("config:", "").replace(".value", "")
        return Config(name)
    return _metric_to_frontend(x)


def _metric_to_backend_groupby(val: Optional[Union[str, "Config"]]) -> Optional[str]:
    """
    Normalise a group-by key so the backend always receives the form
        <first_segment>.value[.<rest>]

    Accepts
    --------
    1. wr.Config("epochs")              ➔ "epochs.value"
    2. "config.epochs" / "config.a.b"   ➔ "epochs.value" / "a.value.b"
    3. "epochs" / "a.b"                 ➔ "epochs.value" / "a.value.b"

    Anything that is already in the correct format
    ("epochs.value", "a.value.b", …) is returned unchanged.
    """
    if val is None:
        return None

    # 1) unwrap wr.Config
    if isinstance(val, Config):
        val = val.name

    # 2) drop an explicit "config." prefix for uniform handling
    if val.startswith("config."):
        val = val.split("config.", 1)[1]

    segments = val.split(".")

    # 3) if we already have ".value" immediately after the first segment, keep it
    if len(segments) >= 2 and segments[1] == "value":
        return val

    first, *rest = segments
    rest_path = "." + ".".join(rest) if rest else ""
    return f"{first}.value{rest_path}"


def _metric_to_frontend_groupby(val: Optional[str]):
    """
    Convert the backend form back into a user-friendly object.
        "epochs.value"   ➔ Config("epochs")
        "a.value.b"      ➔ Config("a.b")
    Anything that isn’t a config path (doesn’t have '.value' as the second
    token) is returned unchanged.
    """
    if val is None or not isinstance(val, str):
        return val

    parts = val.split(".")
    if len(parts) < 2 or parts[1] != "value":
        return val  # not a config key, just return as-is

    first = parts[0]
    rest = parts[2:]
    path = first + ("." + ".".join(rest) if rest else "")
    return Config(path)


def _get_rs_by_name(runsets, name):
    for rs in runsets:
        if rs.name == name:
            return rs


def _get_rs_by_id(runsets, id):
    for rs in runsets:
        if rs._id == id:
            return rs


def _to_color_dict(custom_run_colors, runsets):
    d = {}
    for k, v in custom_run_colors.items():
        if isinstance(k, RunsetGroup):
            rs = _get_rs_by_name(runsets, k.runset_name)
            if not rs:
                continue
            id = rs._id
            kvs = []
            for keys in k.keys:
                kk = _metric_to_backend_panel_grid(keys.key)
                vv = keys.value
                kv = f"{kk}:{vv}"
                kvs.append(kv)
            linked = "-".join(kvs)
            key = f"{id}-{linked}"
        else:
            key = k
        d[key] = v

    return d


def _from_color_dict(d, runsets):
    d2 = {}
    for k, v in d.items():
        id, *backend_parts = k.split("-")

        if backend_parts:
            groups = []
            for part in backend_parts:
                key, value = part.rsplit(":", 1)
                kkey = _metric_to_frontend_panel_grid(key)
                group = RunsetGroupKey(kkey, value)
                groups.append(group)
            rs = _get_rs_by_id(runsets, id)
            rg = RunsetGroup(runset_name=rs.name, keys=groups)
            new_key = rg
        else:
            new_key = k
        d2[new_key] = v
    return d2
