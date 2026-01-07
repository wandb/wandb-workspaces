import sys
from typing import Any, Dict, Generic, Type, TypeVar
from unittest.mock import Mock

import pytest
from polyfactory.factories import DataclassFactory
from polyfactory.pytest_plugin import register_fixture

import wandb_workspaces.reports.v2 as wr
from wandb_workspaces.expr import expr_to_filters, Filters, Key

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

    @classmethod
    def gallery_axis(cls):
        # Don't generate gallery_axis to avoid conflict with grid axes
        return None

    @classmethod
    def grid_x_axis(cls):
        # Don't generate grid axes to avoid conflict with gallery_axis
        return None

    @classmethod
    def grid_y_axis(cls):
        # Don't generate grid axes to avoid conflict with gallery_axis
        return None


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


def test_media_browser_grid_axes():
    """Test that MediaBrowser correctly handles grid axis configuration."""
    # Test creating MediaBrowser with grid axes
    panel = wr.MediaBrowser(
        title="Test Media",
        media_keys=["images"],
        grid_x_axis="step",
        grid_y_axis="run",
    )

    # Convert to model
    model = panel._to_model()

    # Verify the config has grid_settings and mode is set to "grid"
    assert model.config.grid_settings is not None
    assert model.config.grid_settings.x_axis == "step"
    assert model.config.grid_settings.y_axis == "run"
    assert model.config.mode == "grid"

    # Test round-trip conversion
    restored = wr.MediaBrowser._from_model(model)
    assert restored.grid_x_axis == "step"
    assert restored.grid_y_axis == "run"
    assert restored.media_keys == ["images"]


def test_media_browser_grid_axes_none():
    """Test that MediaBrowser works when grid axes are not specified."""
    panel = wr.MediaBrowser(title="Test Media", media_keys=["image"])

    # Convert to model
    model = panel._to_model()

    # Verify no grid_settings when axes are None and mode is not set
    assert model.config.grid_settings is None
    assert model.config.mode is None

    # Test round-trip conversion
    restored = wr.MediaBrowser._from_model(model)
    assert restored.grid_x_axis is None
    assert restored.grid_y_axis is None


def test_media_browser_grid_axes_partial():
    """Test that MediaBrowser handles partial grid axis configuration."""
    panel = wr.MediaBrowser(
        title="Test Media", media_keys=["video"], grid_x_axis="index"
    )

    # Convert to model
    model = panel._to_model()

    # Verify grid_settings is created even with partial config and mode is set to "grid"
    assert model.config.grid_settings is not None
    assert model.config.grid_settings.x_axis == "index"
    assert model.config.grid_settings.y_axis is None
    assert model.config.mode == "grid"

    # Test round-trip conversion
    restored = wr.MediaBrowser._from_model(model)
    assert restored.grid_x_axis == "index"
    assert restored.grid_y_axis is None


def test_media_browser_gallery_axis():
    """Test that MediaBrowser correctly handles gallery axis configuration."""
    panel = wr.MediaBrowser(
        title="Test Media Gallery",
        media_keys=["images"],
        gallery_axis="step",
    )

    # Convert to model
    model = panel._to_model()

    # Verify the config has gallery_settings and mode is auto-set to "gallery"
    assert model.config.gallery_settings is not None
    assert model.config.gallery_settings.axis == "step"
    assert model.config.mode == "gallery"

    # Test round-trip conversion preserves mode
    restored = wr.MediaBrowser._from_model(model)
    assert restored.gallery_axis == "step"
    assert restored.mode == "gallery"
    assert restored.grid_x_axis is None
    assert restored.grid_y_axis is None


def test_media_browser_mode_conflict():
    """Test that MediaBrowser raises error when both gallery and grid axes are set without mode."""
    with pytest.raises(ValueError, match="Must specify 'mode' parameter"):
        panel = wr.MediaBrowser(
            title="Test Media",
            media_keys=["images"],
            gallery_axis="step",
            grid_x_axis="step",
            grid_y_axis="run",
        )
        panel._to_model()


def test_media_browser_explicit_mode_with_both_axes():
    """Test that MediaBrowser works when mode is explicitly set with both axes."""
    # Use grid mode even though gallery_axis is also set
    panel = wr.MediaBrowser(
        title="Test Media",
        media_keys=["images"],
        mode="grid",
        gallery_axis="step",
        grid_x_axis="step",
        grid_y_axis="run",
    )

    model = panel._to_model()

    # Verify grid mode is used
    assert model.config.mode == "grid"
    assert model.config.grid_settings is not None
    assert model.config.gallery_settings is not None

    # Test round-trip
    restored = wr.MediaBrowser._from_model(model)
    assert restored.mode == "grid"


def test_runset_query_parameter():
    """Test that Runset query parameter is properly passed through to internal model"""
    from wandb_workspaces.reports.v2 import internal

    # Test _to_model() - query parameter should be passed to internal model
    runset = wr.Runset(query="test-run-name")
    model = runset._to_model()
    assert model.search is not None
    assert model.search.query == "test-run-name"

    # Test empty query string
    runset_empty = wr.Runset(query="")
    model_empty = runset_empty._to_model()
    assert model_empty.search is not None
    assert model_empty.search.query == ""

    # Test _from_model() - query parameter should be reconstructed from internal model
    # Create a mock internal runset with search
    mock_search = internal.RunsetSearch(query="reconstructed-query")
    mock_runset = internal.Runset(name="test", search=mock_search)

    reconstructed = wr.Runset._from_model(mock_runset)
    assert reconstructed.query == "reconstructed-query"

    # Test _from_model() with empty search object
    mock_empty_search = internal.RunsetSearch(query="")
    mock_runset_empty_search = internal.Runset(name="test", search=mock_empty_search)
    reconstructed_empty_search = wr.Runset._from_model(mock_runset_empty_search)
    assert reconstructed_empty_search.query == ""


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
        assert (
            result == expected
        ), f"Input: {input_val!r}, Expected: {expected!r}, Got: {result!r}"


def test_metric_to_frontend_groupby():
    """Test the _metric_to_frontend_groupby function"""

    test_cases = [
        ("epochs.value", wr.Config("epochs")),
        ("keys.value.key1", wr.Config("keys.key1")),
        ("non_config_path", "non_config_path"),  # Should pass through unchanged
        (None, None),
        ("None", "None"),
    ]

    for input_val, expected in test_cases:
        result = wr.interface._metric_to_frontend_groupby(input_val)
        assert (
            result == expected
        ), f"Input: {input_val!r}, Expected: {expected!r}, Got: {result!r}"


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
        wr.LinePlot(groupby="None", aggregate=False),
        wr.BarPlot(groupby="None", aggregate=False),
    ]

    for panel in panels_without_groupby:
        model = panel._to_model()
        assert model.config.group_by in (None, "None")
        assert model.config.aggregate is False


def test_strip_refs():
    """Test that _strip_refs removes ref fields correctly from nested structures"""
    # Test comprehensive nested structure with proper ref objects
    test_data = {
        "ref": {"viewID": "test123", "type": "panel", "id": "abc123"},
        "panelRef": {"viewID": "test456", "type": "panel", "id": "def456"},
        "sectionRefs": [
            {"viewID": "test789", "type": "section", "id": "ghi789"},
            {"viewID": "test012", "type": "section", "id": "jkl012"},
        ],
        "runSetRef": {"viewID": "test345", "type": "runSet", "id": "mno345"},
        "invalidRef": "should_not_be_removed",  # String, not a ref object
        "partialRef": {"viewID": "test", "type": "missing_id"},  # Missing id
        "normal_field": "should_remain",
        "nested": {
            "ref": {"viewID": "nested123", "type": "panel", "id": "nested_abc"},
            "innerRef": {"viewID": "nested456", "type": "inner", "id": "nested_def"},
            "dataRefs": [
                {"viewID": "data1", "type": "data", "id": "data_1"},
                {"viewID": "data2", "type": "data", "id": "data_2"},
            ],
            "invalidRefs": [1, 2, 3],  # Not ref objects
            "keep_me": "should_remain",
        },
        "list_field": [
            {
                "ref": {"viewID": "list1", "type": "item", "id": "list_1"},
                "data": "keep_me",
            },
            {
                "itemRef": {"viewID": "list2", "type": "item", "id": "list_2"},
                "value": 123,
            },
            {"normalField": "unchanged"},
        ],
    }

    wr.interface._strip_refs(test_data)

    # Check that valid ref fields are removed at top level
    assert "ref" not in test_data
    assert "panelRef" not in test_data
    assert "sectionRefs" not in test_data
    assert "runSetRef" not in test_data

    # Check that invalid refs remain
    assert test_data["invalidRef"] == "should_not_be_removed"
    assert test_data["partialRef"] == {"viewID": "test", "type": "missing_id"}

    # Check that normal fields remain
    assert test_data["normal_field"] == "should_remain"

    # Check nested dict removal
    assert "ref" not in test_data["nested"]
    assert "innerRef" not in test_data["nested"]
    assert "dataRefs" not in test_data["nested"]
    assert test_data["nested"]["invalidRefs"] == [1, 2, 3]  # Should remain
    assert test_data["nested"]["keep_me"] == "should_remain"

    # Check list processing
    assert "ref" not in test_data["list_field"][0]
    assert test_data["list_field"][0]["data"] == "keep_me"
    assert "itemRef" not in test_data["list_field"][1]
    assert test_data["list_field"][1]["value"] == 123
    assert test_data["list_field"][2]["normalField"] == "unchanged"

    # Test edge cases
    wr.interface._strip_refs({})  # Empty dict
    wr.interface._strip_refs([])  # Empty list
    wr.interface._strip_refs("string")  # Non-container types
    wr.interface._strip_refs(None)


def test_url_to_viewspec_strips_refs(monkeypatch):
    """Test that _url_to_viewspec properly strips refs from the spec field"""
    import json

    # Mock the API response with proper ref objects in the spec
    mock_viewspec = {
        "id": "test-id",
        "spec": json.dumps(
            {
                "blocks": [
                    {
                        "type": "panel-grid",
                        "ref": {
                            "viewID": "test123",
                            "type": "panel-grid",
                            "id": "abc123",
                        },
                        "metadata": {
                            "panelBankSectionConfig": {
                                "name": "Charts",
                                "sectionRef": {
                                    "viewID": "test456",
                                    "type": "section",
                                    "id": "def456",
                                },
                            }
                        },
                    }
                ]
            }
        ),
        "topLevelRef": {"viewID": "test789", "type": "view", "id": "ghi789"},
        "invalidRef": "should_remain",  # String, not a ref object
        "normalField": "should_remain",
    }

    mock_client = Mock()
    mock_client.execute.return_value = {"view": mock_viewspec}

    def mock_get_api():
        return type("MockApi", (), {"client": mock_client})()

    monkeypatch.setattr("wandb_workspaces.reports.v2.interface._get_api", mock_get_api)

    # Call _url_to_viewspec
    result = wr.interface._url_to_viewspec(
        "https://wandb.ai/entity/project/reports/test--abc123"
    )

    # Parse the spec field to check refs were removed
    spec_dict = json.loads(result["spec"])

    # Check that refs in spec were removed
    assert "ref" not in spec_dict["blocks"][0]
    assert (
        "sectionRef" not in spec_dict["blocks"][0]["metadata"]["panelBankSectionConfig"]
    )

    # Check that top-level ref was removed
    assert "topLevelRef" not in result

    # Check that invalid ref remains (it's a string, not a ref object)
    assert result["invalidRef"] == "should_remain"

    # Check that normal fields remain
    assert result["normalField"] == "should_remain"
    assert (
        spec_dict["blocks"][0]["metadata"]["panelBankSectionConfig"]["name"] == "Charts"
    )


def test_lineplot_xaxis_format():
    """Test LinePlot xaxis_format parameter with lowercase datetime."""
    # Test basic usage
    lp = wr.LinePlot(y=["loss"], xaxis_format="datetime")
    assert lp._to_model().config.x_axis_format == "datetime"

    # Test with custom metric
    lp2 = wr.LinePlot(x="timestamp", y=["loss"], xaxis_format="datetime")
    assert lp2._to_model().config.x_axis_format == "datetime"

    # Test None case
    lp3 = wr.LinePlot(y=["loss"])
    assert lp3._to_model().config.x_axis_format is None

    # Test round-trip serialization
    model = lp._to_model()
    reconstructed = wr.LinePlot._from_model(model)
    assert reconstructed.xaxis_format == "datetime"


def test_lineplot_metric_regex():
    """Test LinePlot metric_regex parameter for regex-based y-axis metric selection."""
    # Test basic usage with metric_regex
    lp = wr.LinePlot(
        y=["loss"],
        metric_regex="system/.*",
    )
    assert lp._to_model().config.metric_regex == "system/.*"
    assert lp._to_model().config.use_metric_regex is True  # Auto-set internally

    # Test with only metric_regex set
    lp2 = wr.LinePlot(metric_regex="train/.*")
    assert lp2._to_model().config.metric_regex == "train/.*"
    assert lp2._to_model().config.use_metric_regex is True  # Auto-set internally

    # Test None case (default)
    lp3 = wr.LinePlot(y=["loss"])
    assert lp3._to_model().config.metric_regex is None
    assert lp3._to_model().config.use_metric_regex is None

    # Test round-trip serialization
    model = lp._to_model()
    reconstructed = wr.LinePlot._from_model(model)
    assert reconstructed.metric_regex == "system/.*"

    # Verify that setting metric_regex results in use_metric_regex=True in the backend
    lp4 = wr.LinePlot(
        y=["loss"],
        metric_regex="val/.*",
    )
    assert lp4._to_model().config.metric_regex == "val/.*"
    assert lp4._to_model().config.use_metric_regex is True


def test_block_validation_no_unknown_blocks():
    """Test that blocks are parsed correctly without creating UnknownBlock instances."""
    from wandb_workspaces.reports.v2 import internal

    # Simulate a report spec with various block types
    test_spec_dict = {
        "id": "test-report",
        "name": "test-report",
        "displayName": "Test Report",
        "description": "A test report",
        "project": {
            "name": "test-project",
            "entityName": "test-entity",
        },
        "spec": {
            "version": 5,
            "panelSettings": {},
            "blocks": [
                {
                    "type": "heading",
                    "level": 1,
                    "children": [{"text": "Test Heading"}],
                },
                {
                    "type": "paragraph",
                    "children": [{"text": "This is a test paragraph."}],
                },
                {
                    "type": "code-block",
                    "language": "python",
                    "children": [
                        {
                            "type": "code-line",
                            "children": [{"text": "print('Hello, World!')"}],
                        }
                    ],
                },
            ],
            "width": "readable",
            "authors": [],
            "discussionThreads": [],
        },
    }

    model = internal.ReportViewspec.model_validate(test_spec_dict)
    assert len(model.spec.blocks) == 3

    # Ensure no blocks are UnknownBlock
    for block in model.spec.blocks:
        assert not isinstance(
            block, internal.UnknownBlock
        ), f"Block should not be UnknownBlock, got {type(block).__name__}"

    # Verify specific block types
    assert isinstance(model.spec.blocks[0], internal.Heading)
    assert isinstance(model.spec.blocks[1], internal.Paragraph)
    assert isinstance(model.spec.blocks[2], internal.CodeBlock)


def test_unordered_list_complex_items():
    """Test that UnorderedList can handle items with multiple text segments."""
    from wandb_workspaces.reports.v2 import internal

    test_spec_dict = {
        "id": "test-report",
        "name": "test-report",
        "displayName": "Test Report",
        "description": "A test report",
        "project": {
            "name": "test-project",
            "entityName": "test-entity",
        },
        "spec": {
            "version": 5,
            "panelSettings": {},
            "blocks": [
                {
                    "type": "list",
                    "ordered": False,
                    "children": [
                        {
                            "type": "list-item",
                            "children": [
                                {
                                    "type": "paragraph",
                                    "children": [{"text": "Simple item"}],
                                }
                            ],
                        },
                        {
                            "type": "list-item",
                            "children": [
                                {
                                    "type": "paragraph",
                                    "children": [
                                        {"text": "Base Model"},
                                        {"text": ": OpenPipe/Qwen3-14B-Instruct"},
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ],
            "width": "readable",
            "authors": [],
            "discussionThreads": [],
        },
    }

    # Should not raise validation error
    model = internal.ReportViewspec.model_validate(test_spec_dict)
    assert len(model.spec.blocks) == 1
    assert isinstance(model.spec.blocks[0], internal.List)
    assert len(model.spec.blocks[0].children) == 2


def test_ordered_list_complex_items():
    """Test that OrderedList can handle items with multiple text segments."""
    from wandb_workspaces.reports.v2 import internal

    test_spec_dict = {
        "id": "test-report",
        "name": "test-report",
        "displayName": "Test Report",
        "description": "A test report",
        "project": {
            "name": "test-project",
            "entityName": "test-entity",
        },
        "spec": {
            "version": 5,
            "panelSettings": {},
            "blocks": [
                {
                    "type": "list",
                    "ordered": True,
                    "children": [
                        {
                            "type": "list-item",
                            "ordered": True,
                            "children": [
                                {
                                    "type": "paragraph",
                                    "children": [{"text": "First"}, {"text": " item"}],
                                }
                            ],
                        },
                        {
                            "type": "list-item",
                            "ordered": True,
                            "children": [
                                {
                                    "type": "paragraph",
                                    "children": [
                                        {"text": "Second"},
                                        {"text": " item"},
                                        {"text": " with more"},
                                    ],
                                }
                            ],
                        },
                    ],
                }
            ],
            "width": "readable",
            "authors": [],
            "discussionThreads": [],
        },
    }

    # Should not raise validation error
    model = internal.ReportViewspec.model_validate(test_spec_dict)
    assert len(model.spec.blocks) == 1
    assert isinstance(model.spec.blocks[0], internal.List)
    assert len(model.spec.blocks[0].children) == 2


# Tests for Runset.custom_run_colors being merged into PanelGrid
class TestRunsetCustomRunColors:
    """Tests for custom_run_colors on Runset being properly merged into PanelGrid."""

    @pytest.fixture(autouse=True)
    def mock_api(self, monkeypatch):
        """Mock the wandb API to avoid network calls."""
        mock_client = Mock()
        mock_client.execute.return_value = {
            "project": {"internalId": "test-project-id"}
        }
        monkeypatch.setattr(
            "wandb_workspaces.reports.v2.interface._get_api",
            lambda: type("MockApi", (), {"client": mock_client})(),
        )

    def test_runset_colors_applied_to_panel_grid(self):
        """Colors defined on Runset should be included in PanelGrid._to_model()."""
        runset = wr.Runset(
            entity="test",
            project="test",
            custom_run_colors={"run-1": "#FF0000", "run-2": "#00FF00"},
        )
        panel_grid = wr.PanelGrid(runsets=[runset])

        model = panel_grid._to_model()

        assert model.metadata.custom_run_colors == {
            "run-1": "#FF0000",
            "run-2": "#00FF00",
        }

    def test_panel_grid_colors_override_runset_colors(self):
        """PanelGrid colors should take precedence over Runset colors."""
        runset = wr.Runset(
            entity="test",
            project="test",
            custom_run_colors={"run-1": "#FF0000", "run-2": "#00FF00"},
        )
        panel_grid = wr.PanelGrid(
            runsets=[runset],
            custom_run_colors={"run-1": "#0000FF"},  # Override run-1
        )

        model = panel_grid._to_model()

        assert model.metadata.custom_run_colors == {
            "run-1": "#0000FF",  # PanelGrid color wins
            "run-2": "#00FF00",  # Runset color preserved
        }

    def test_multiple_runsets_colors_merged(self):
        """Colors from multiple runsets should all be merged."""
        runset1 = wr.Runset(
            entity="test",
            project="test",
            custom_run_colors={"run-1": "#FF0000"},
        )
        runset2 = wr.Runset(
            entity="test",
            project="test",
            custom_run_colors={"run-2": "#00FF00"},
        )
        panel_grid = wr.PanelGrid(runsets=[runset1, runset2])

        model = panel_grid._to_model()

        assert model.metadata.custom_run_colors == {
            "run-1": "#FF0000",
            "run-2": "#00FF00",
        }
        
# Tests for _from_color_dict edge cases (migration bug fixes)
class TestFromColorDict:
    """Tests for _from_color_dict handling of edge cases during report migration."""

    def test_plain_run_id_with_dashes(self):
        """Run IDs with dashes (e.g., 'abc-123') should not be parsed as RunsetGroup."""
        from wandb_workspaces.reports.v2.interface import _from_color_dict

        # Plain run ID with dashes - no colons means it's not a RunsetGroup
        color_dict = {"abc-123-def": "#FF0000", "simple": "#00FF00"}
        result = _from_color_dict(color_dict, runsets=[])

        # Both keys should be preserved as-is (not parsed as RunsetGroup)
        assert result == {"abc-123-def": "#FF0000", "simple": "#00FF00"}

    def test_missing_runset_preserves_key(self):
        """When runset ID not found, preserve original key instead of crashing."""
        from wandb_workspaces.reports.v2.interface import _from_color_dict

        # Valid RunsetGroup format but runset doesn't exist
        color_dict = {"nonexistent-runset-config:value": "#FF0000"}
        result = _from_color_dict(color_dict, runsets=[])

        # Key should be preserved when runset lookup fails
        assert result == {"nonexistent-runset-config:value": "#FF0000"}

    def test_valid_runset_group_format(self):
        """Valid RunsetGroup format with existing runset should parse correctly."""
        from wandb_workspaces.reports.v2.interface import _from_color_dict

        # Create a mock runset with matching _id
        mock_runset = wr.Runset(entity="test", project="test", name="My Runset")
        # Access private _id field
        runset_id = mock_runset._id

        color_dict = {f"{runset_id}-config:lr": "#FF0000"}
        result = _from_color_dict(color_dict, runsets=[mock_runset])

        # Should parse into RunsetGroup
        assert len(result) == 1
        key = list(result.keys())[0]
        assert isinstance(key, wr.RunsetGroup)
        assert key.runset_name == "My Runset"
        assert result[key] == "#FF0000"
