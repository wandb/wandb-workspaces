import sys
from typing import Any, Dict, Generic, Type, TypeVar
from unittest.mock import Mock

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

    @classmethod
    def chart_fields(cls):
        return {"x": "x", "y": "y"}

    @classmethod
    def chart_strings(cls):
        return {"x": "x-axis", "y": "y-axis"}


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

    model = instance._to_model()
    model2 = cls._from_model(model)._to_model()

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
            "b == 1 and c == 2",
            [
                Filters(
                    op="==",
                    key=Key(section="run", name="b"),
                    filters=None,
                    value=1,
                    disabled=False,
                ),
                Filters(
                    op="==",
                    key=Key(section="run", name="c"),
                    filters=None,
                    value=2,
                    disabled=False,
                ),
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


def test_layout_config():
    DEFAULT_LAYOUT = {
        "x": wr.Layout.x,
        "y": wr.Layout.y,
        "w": wr.Layout.w,
        "h": wr.Layout.h,
    }
    CUSTOM_USER_DEFINED_LAYOUT = {"x": 0, "y": 0, "w": 24, "h": 24}

    p0 = wr.WeavePanelSummaryTable(table_name="test")
    p1 = wr.WeavePanelSummaryTable(table_name="test", layout=CUSTOM_USER_DEFINED_LAYOUT)
    p2 = wr.WeavePanelArtifact(artifact="test", layout=CUSTOM_USER_DEFINED_LAYOUT)
    p3 = wr.WeavePanelArtifactVersionedFile(
        artifact="test",
        version="vtest",
        file="test.txt",
        layout=CUSTOM_USER_DEFINED_LAYOUT,
    )
    p4 = wr.WeavePanel(layout=CUSTOM_USER_DEFINED_LAYOUT)

    assert p0._to_model().layout.model_dump() == DEFAULT_LAYOUT

    for panel in [p1, p2, p3, p4]:
        assert panel._to_model().layout.model_dump() == CUSTOM_USER_DEFINED_LAYOUT


def test_url_to_report_id_padding():
    import base64
    import wandb_workspaces.reports.v2 as wr

    # "test" -> base64 encoded becomes "dGVzdA=="
    original = b"test"
    encoded = base64.b64encode(original).decode("utf-8")  # "dGVzdA=="
    # Remove the '=' padding to simulate a URL-embedded report id.
    stripped = encoded.replace("=", "")

    # Construct a fake URL in the expected format:
    #   http://wandb.ai/{entity}/{project}/reports/{title}--{report_id}
    url = f"http://wandb.ai/my_entity/my_project/reports/my-report--{stripped}"

    # Call the function and verify that the returned id matches the properly padded version.
    result = wr.interface._url_to_report_id(url)
    assert result == encoded, f"Expected {encoded} but got {result}"


def test_codeblock_multiline_round_trip():
    """
    Ensure that CodeBlock._to_model and _from_model correctly round-trip
    multi-line code strings without losing blank lines.
    """
    lines = ["import wandb", "", "wandb.init()"]
    code_str = "\n".join(lines)
    # Create an interface CodeBlock with multilines
    block = wr.CodeBlock(code=code_str)
    # Convert to internal model and back
    model = block._to_model()
    restored = wr.CodeBlock._from_model(model)
    # The code and language should be identical after round-trip
    assert restored.code == code_str
    assert restored.language == block.language


def test_report_delete(monkeypatch):
    """Create a dummy report, monkey-patch the internal _get_api call, and verify
    that the Report.delete method sends the expected GraphQL mutation and
    returns True when the backend acknowledges success."""

    # Track the arguments that the mocked `execute` receives for later assertions
    captured: Dict[str, Any] = {}

    class _DummyClient:
        def execute(self, query, *, variable_values):  # type: ignore
            # Save inputs so the test can inspect them later
            captured["query"] = query
            captured["variables"] = variable_values
            # Simulate a successful deleteView response from the backend
            return {"deleteView": {"success": True}}

    class _DummyApi:
        def __init__(self):
            self.client = _DummyClient()

    # Monkey-patch the private helper used by Report.delete so that no real
    # network calls are made.
    monkeypatch.setattr(wr.interface, "_get_api", lambda: _DummyApi())

    # Create a Report instance and manually assign an id so that .delete() works
    report = wr.Report(project="proj", entity="ent")
    report.id = "dummy-id"

    # Call delete and assert it returns True (success)
    assert report.delete() is True

    # Ensure the GraphQL mutation received the correct variables (deleteDrafts always True)
    assert captured["variables"] == {"id": "dummy-id", "deleteDrafts": True}


def test_runset_project_lookup(monkeypatch):
    """Test that Runset._to_model() correctly handles project ID lookup"""
    # Mock the wandb API client
    mock_client = Mock()

    def mock_get_api():
        return type("MockApi", (), {"client": mock_client})()

    monkeypatch.setattr("wandb_workspaces.reports.v2.interface._get_api", mock_get_api)

    # Test successful case - project exists and ID is added
    mock_client.execute.return_value = {
        "project": {"internalId": "UHJvamVjdEludGVybmFsSWQ6MTIzNDU="}
    }
    runset = wr.Runset(entity="test-entity", project="test-project")
    model = runset._to_model()
    assert model.project.entity_name == "test-entity"
    assert model.project.name == "test-project"
    assert model.project.id == "UHJvamVjdEludGVybmFsSWQ6MTIzNDU="

    # Test error case - project not found
    mock_client.execute.return_value = {"project": None}
    with pytest.raises(ValueError) as exc_info:
        wr.Runset(entity="bad-entity", project="bad-project")._to_model()
    assert "project 'bad-entity/bad-project' not found" in str(exc_info.value)


def test_metric_to_backend_groupby():
    """Test the _metric_to_backend_groupby function with various input formats"""
    
    # Test cases: (input, expected_output)
    test_cases = [
        # Core functionality - what users will actually use
        (wr.Config("epochs"), "epochs.value"),
        (wr.Config("keys.key1"), "keys.value.key1"),
        ("config.epochs", "epochs.value"),
        ("epochs", "epochs.value"),
        ("keys.key1", "keys.value.key1"),
        
        # Edge cases
        (None, None),
        ("", ".value"),
    ]
    
    for input_val, expected in test_cases:
        result = wr.interface._metric_to_backend_groupby(input_val)
        assert result == expected, f"Input: {input_val!r}, Expected: {expected!r}, Got: {result!r}"


def test_metric_to_frontend_groupby():
    """Test the _metric_to_frontend_groupby function"""
    
    test_cases = [
        ("epochs.value", wr.Config("epochs")),
        ("keys.value.key1", wr.Config("keys.key1")),
        ("non_config_path", "non_config_path"),  # Should pass through unchanged
        (None, None),
    ]
    
    for input_val, expected in test_cases:
        result = wr.interface._metric_to_frontend_groupby(input_val)
        assert result == expected, f"Input: {input_val!r}, Expected: {expected!r}, Got: {result!r}"


def test_groupby_aggregate_behavior():
    """Test that panels automatically set aggregate=True when groupby is specified"""
    
    # Test that any panel with groupby automatically sets aggregate=True
    panels_with_groupby = [
        wr.LinePlot(groupby=wr.Config("epochs")),
        wr.LinePlot(groupby="epochs"),
        wr.BarPlot(groupby=wr.Config("epochs")),
        wr.BarPlot(groupby="epochs"),
    ]
    
    for panel in panels_with_groupby:
        model = panel._to_model()
        assert model.config.group_by == "epochs.value"
        assert model.config.aggregate is True
    
    # Test that panels without groupby can control aggregate manually
    panels_without_groupby = [
        wr.LinePlot(groupby=None, aggregate=False),
        wr.BarPlot(groupby=None, aggregate=False),
    ]
    
    for panel in panels_without_groupby:
        model = panel._to_model()
        assert model.config.group_by is None
        assert model.config.aggregate is False
