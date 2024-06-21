import sys
from typing import Any, Dict, Generic, Type, TypeVar

import pytest
from polyfactory.factories import DataclassFactory
from polyfactory.pytest_plugin import register_fixture

import wandb_workspaces.reports.v2 as wr
from wandb_workspaces.reports.v2.expr_parsing import expr_to_filters
from wandb_workspaces.reports.v2.internal import Filters, Key

T = TypeVar("T")


class CustomDataclassFactory(Generic[T], DataclassFactory[T]):
    __is_base_factory__ = True
    # __random_seed__ = 123

    @classmethod
    def get_provider_map(cls) -> Dict[Type, Any]:
        providers_map = super().get_provider_map()

        return {
            "TextLikeField": lambda: "",  # type: ignore
            "BlockTypes": lambda: wr.H1(),  # type: ignore
            "PanelTypes": lambda: wr.LinePlot(),  # type: ignore
            "AnyUrl": lambda: "https://link.com",  # type: ignore
            **providers_map,
        }


class GradientPointFactory(CustomDataclassFactory[wr.GradientPoint]):
    __model__ = wr.GradientPoint

    @classmethod
    def color(cls):
        return "#FFFFFF"


class ParallelCoordinatesPlotColumnFactory(
    CustomDataclassFactory[wr.ParallelCoordinatesPlotColumn]
):
    __model__ = wr.ParallelCoordinatesPlotColumn

    @classmethod
    def metric(cls):
        return wr.Config("test")


@register_fixture
class H1Factory(CustomDataclassFactory[wr.H1]):
    __model__ = wr.H1

    @classmethod
    def collapsed_blocks(cls):
        return None


@register_fixture
class H2Factory(CustomDataclassFactory[wr.H2]):
    __model__ = wr.H2

    @classmethod
    def collapsed_blocks(cls):
        return None


@register_fixture
class H3Factory(CustomDataclassFactory[wr.H3]):
    __model__ = wr.H3

    @classmethod
    def collapsed_blocks(cls):
        return None


@register_fixture
class BlockQuoteFactory(CustomDataclassFactory[wr.BlockQuote]):
    __model__ = wr.BlockQuote


@register_fixture
class CalloutBlockFactory(CustomDataclassFactory[wr.CalloutBlock]):
    __model__ = wr.CalloutBlock


@register_fixture
class CheckedListFactory(CustomDataclassFactory[wr.CheckedList]):
    __model__ = wr.CheckedList


@register_fixture
class CodeBlockFactory(CustomDataclassFactory[wr.CodeBlock]):
    __model__ = wr.CodeBlock


@register_fixture
class GalleryFactory(CustomDataclassFactory[wr.Gallery]):
    __model__ = wr.Gallery


@register_fixture
class HorizontalRuleFactory(CustomDataclassFactory[wr.HorizontalRule]):
    __model__ = wr.HorizontalRule


@register_fixture
class ImageFactory(CustomDataclassFactory[wr.Image]):
    __model__ = wr.Image


@register_fixture
class LatexBlockFactory(CustomDataclassFactory[wr.LatexBlock]):
    __model__ = wr.LatexBlock


@register_fixture
class MarkdownBlockFactory(CustomDataclassFactory[wr.MarkdownBlock]):
    __model__ = wr.MarkdownBlock


@register_fixture
class OrderedListFactory(CustomDataclassFactory[wr.OrderedList]):
    __model__ = wr.OrderedList


@register_fixture
class PFactory(CustomDataclassFactory[wr.P]):
    __model__ = wr.P


@register_fixture
class PanelGridFactory(CustomDataclassFactory[wr.PanelGrid]):
    __model__ = wr.PanelGrid

    @classmethod
    def panels(cls):
        return [wr.LinePlot()]

    @classmethod
    def runsets(cls):
        return [
            wr.Runset(filters="a >= 1"),
            wr.Runset(filters="b == 1 and c == 2"),
        ]


@register_fixture
class TableOfContentsFactory(CustomDataclassFactory[wr.TableOfContents]):
    __model__ = wr.TableOfContents


@register_fixture
class UnorderedListFactory(CustomDataclassFactory[wr.UnorderedList]):
    __model__ = wr.UnorderedList


@register_fixture
class VideoFactory(CustomDataclassFactory[wr.Video]):
    __model__ = wr.Video


@register_fixture
class BarPlotFactory(CustomDataclassFactory[wr.BarPlot]):
    __model__ = wr.BarPlot


@register_fixture
class CodeComparerFactory(CustomDataclassFactory[wr.CodeComparer]):
    __model__ = wr.CodeComparer


@register_fixture
class CustomChartFactory(CustomDataclassFactory[wr.CustomChart]):
    __model__ = wr.CustomChart

    @classmethod
    def query(cls):
        return {"history": {"keys": ["x", "y"], "id": None, "name": None}}


@register_fixture
class LinePlotFactory(CustomDataclassFactory[wr.LinePlot]):
    __model__ = wr.LinePlot


@register_fixture
class MarkdownPanelFactory(CustomDataclassFactory[wr.MarkdownPanel]):
    __model__ = wr.MarkdownPanel


@register_fixture
class MediaBrowserFactory(CustomDataclassFactory[wr.MediaBrowser]):
    __model__ = wr.MediaBrowser


@register_fixture
class ParallelCoordinatesPlotFactory(
    CustomDataclassFactory[wr.ParallelCoordinatesPlot]
):
    __model__ = wr.ParallelCoordinatesPlot

    @classmethod
    def gradient(cls):
        return [GradientPointFactory.build()]

    @classmethod
    def columns(cls):
        return [ParallelCoordinatesPlotColumnFactory.build()]


@register_fixture
class ParameterImportancePlotFactory(
    CustomDataclassFactory[wr.ParameterImportancePlot]
):
    __model__ = wr.ParameterImportancePlot


@register_fixture
class RunComparerFactory(CustomDataclassFactory[wr.RunComparer]):
    __model__ = wr.RunComparer


@register_fixture
class ScalarChartFactory(CustomDataclassFactory[wr.ScalarChart]):
    __model__ = wr.ScalarChart


@register_fixture
class ScatterPlotFactory(CustomDataclassFactory[wr.ScatterPlot]):
    __model__ = wr.ScatterPlot

    @classmethod
    def gradient(cls):
        gradient_point = GradientPointFactory.build()
        return [gradient_point]


block_factory_names = [
    "h1_factory",
    "h2_factory",
    "h3_factory",
    "block_quote_factory",
    "callout_block_factory",
    "checked_list_factory",
    "code_block_factory",
    "gallery_factory",
    "horizontal_rule_factory",
    "image_factory",
    "latex_block_factory",
    "markdown_block_factory",
    "ordered_list_factory",
    "p_factory",
    "panel_grid_factory",
    "table_of_contents_factory",
    "unordered_list_factory",
    "video_factory",
]

panel_factory_names = [
    "bar_plot_factory",
    "code_comparer_factory",
    "custom_chart_factory",
    "line_plot_factory",
    "markdown_panel_factory",
    "media_browser_factory",
    "parallel_coordinates_plot_factory",
    "parameter_importance_plot_factory",
    "run_comparer_factory",
    "scalar_chart_factory",
    "scatter_plot_factory",
]

factory_names = block_factory_names + panel_factory_names


@pytest.mark.skipif(
    sys.version_info < (3, 8), reason="polyfactory requires py38 or higher"
)
@pytest.mark.parametrize("factory_name", factory_names)
def test_idempotency(request, factory_name) -> None:
    factory = request.getfixturevalue(factory_name)
    instance = factory.build()

    cls = factory.__model__
    assert isinstance(instance, cls)

    model = instance.to_model()
    model2 = cls.from_model(model).to_model()

    assert model.dict() == model2.dict()


def test_fix_panel_collisions():
    p1 = wr.interface.Panel(layout=wr.Layout(0, 0, 8, 6))
    p2 = wr.interface.Panel(layout=wr.Layout(1, 1, 8, 6))
    p3 = wr.interface.Panel(layout=wr.Layout(2, 1, 8, 6))

    panels = [p1, p2, p3]
    panels = wr.interface._resolve_collisions(panels)

    for p1 in panels:
        for p2 in panels[1:]:
            assert not wr.interface._collides(p1, p2)


@pytest.mark.parametrize(
    "expr, expected_filters",
    [
        ["", []],
        [
            "a >= 1",
            [
                Filters(
                    op=">=",
                    key=Key(section="run", name="a"),
                    filters=None,
                    value=1,
                    disabled=False,
                )
            ],
        ],
        [
            "(a >= 1)",
            [
                Filters(
                    op=">=",
                    key=Key(section="run", name="a"),
                    filters=None,
                    value=1,
                    disabled=False,
                )
            ],
        ],
        [
            "(Metric('a') >= 1)",
            [
                Filters(
                    op=">=",
                    key=Key(section="run", name="a"),
                    filters=None,
                    value=1,
                    disabled=False,
                )
            ],
        ],
        [
            "(SummaryMetric('a') >= 1)",
            [
                Filters(
                    op=">=",
                    key=Key(section="summary", name="a"),
                    filters=None,
                    value=1,
                    disabled=False,
                )
            ],
        ],
        [
            "(Config('a') >= 1)",
            [
                Filters(
                    op=">=",
                    key=Key(section="config", name="a"),
                    filters=None,
                    value=1,
                    disabled=False,
                )
            ],
        ],
    ],
)
def test_expression_parsing(expr, expected_filters):
    assert expr_to_filters(expr) == Filters(
        op="OR", filters=[Filters(op="AND", filters=expected_filters)]
    )
