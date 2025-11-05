import os
import sys
from typing import Any, Dict, Generic, Type, TypeVar
from unittest.mock import Mock, patch

import pytest
from polyfactory.factories import DataclassFactory
from polyfactory.pytest_plugin import register_fixture
import wandb_workspaces.reports.v2.internal as _wr
import wandb_workspaces.expr
import wandb_workspaces.reports.v2 as wr
import wandb_workspaces.workspaces as ws
from tests.weave_panel_factory import WeavePanelFactory
from wandb_workspaces.utils.validators import (
    validate_no_emoji,
    validate_spec_version,
    validate_url,
)
from wandb_workspaces.workspaces.errors import SpecVersionError, UnsupportedViewError

T = TypeVar("T")


class CustomDataclassFactory(Generic[T], DataclassFactory[T]):
    __is_base_factory__ = True
    # __random_seed__ = 123

    @classmethod
    def get_provider_map(cls) -> Dict[Type, Any]:
        providers_map = super().get_provider_map()

        return {
            "FilterExpr": lambda: wandb_workspaces.expr.Metric("abc") > 1,  # type: ignore
            **providers_map,
        }


@register_fixture
class WorkspaceFactory(CustomDataclassFactory[ws.Workspace]):
    __model__ = ws.Workspace

    @classmethod
    def runset_settings(cls):
        return ws.RunsetSettings(
            filters=[
                wandb_workspaces.expr.Metric("abc") > 1,
                wandb_workspaces.expr.Metric("def") < 2,
                wandb_workspaces.expr.Metric("ghi") >= 3,
                wandb_workspaces.expr.Metric("jkl") <= 4,
                wandb_workspaces.expr.Metric("mno") == "tomato",
                wandb_workspaces.expr.Metric("pqr") != "potato",
                wandb_workspaces.expr.Metric("stu").isin([5, 6, 7, "chicken"]),
                wandb_workspaces.expr.Metric("vwx").notin([8, 9, 0, "broccoli"]),
            ],
        )

    @classmethod
    def sections(cls):
        return [
            ws.Section(name="section1", panels=[wr.LinePlot()]),
            ws.Section(name="section2", panels=[wr.BarPlot(title="tomato")]),
        ]


@register_fixture
class SectionFactory(CustomDataclassFactory[ws.Section]):
    __model__ = ws.Section

    @classmethod
    def panels(cls):
        return [wr.LinePlot()]


@register_fixture
class SectionLayoutSettingsFactory(CustomDataclassFactory[ws.SectionLayoutSettings]):
    __model__ = ws.SectionLayoutSettings


@register_fixture
class SectionPanelSettingsFactory(CustomDataclassFactory[ws.SectionPanelSettings]):
    __model__ = ws.SectionPanelSettings


factory_names = [
    "workspace_factory",
    "section_factory",
    "section_panel_settings_factory",
    "section_panel_settings_factory",
]


def create_mock_wandb_api(execute_return_value=None, app_url="https://app.wandb.test"):
    """
    Helper function to create a mocked wandb.Api instance.

    Args:
        execute_return_value: Return value for client.execute() calls.
                             Can be a single value or a list for side_effect.
        app_url: The app URL to return from client.app_url

    Returns:
        tuple: (mock_api_instance, mock_client) for assertions
    """
    mock_api_instance = Mock()
    mock_client = Mock()

    if isinstance(execute_return_value, list):
        mock_client.execute.side_effect = execute_return_value
    else:
        mock_client.execute.return_value = execute_return_value

    mock_client.app_url = app_url
    mock_api_instance.client = mock_client

    return mock_api_instance, mock_client


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


@pytest.mark.parametrize(
    "expr, spec",
    [
        (
            wandb_workspaces.expr.Metric("abc") > 1,
            {
                "op": ">=",  # > maps to >= internally
                "key": {"section": "run", "name": "abc"},
                "value": 1,
                "disabled": False,
            },
        ),
        (
            wandb_workspaces.expr.Metric("Name") != "tomato",
            {
                "op": "!=",
                "key": {"section": "run", "name": "displayName"},
                "value": "tomato",
                "disabled": False,
            },
        ),
        (
            wandb_workspaces.expr.Metric("Tags").isin(["ppo", "4pool"]),
            {
                "op": "IN",
                "key": {"section": "run", "name": "tags"},
                "value": ["ppo", "4pool"],
                "disabled": False,
            },
        ),
    ],
)
def test_filter_expr(expr, spec):
    assert expr.to_model().model_dump(by_alias=True, exclude_none=True) == spec


def test_runset_settings_string_filters():
    """Test that RunsetSettings accepts filters as both string and FilterExpr list.

    Note: After unification, filters are always stored internally as strings,
    matching the behavior of Reports v2.
    """
    # Test with single = operator (string input)
    settings1 = ws.RunsetSettings(filters="Config('learning_rate') = 0.001")
    assert isinstance(settings1.filters, str)
    assert "learning_rate" in settings1.filters
    assert "0.001" in settings1.filters

    # Test with == operator (string input)
    settings2 = ws.RunsetSettings(filters="Config('learning_rate') == 0.001")
    assert isinstance(settings2.filters, str)
    assert "learning_rate" in settings2.filters

    # Test with multiple filters (string input)
    settings3 = ws.RunsetSettings(
        filters="Config('optimizer') = 'adam' and SummaryMetric('accuracy') >= 0.9"
    )
    assert isinstance(settings3.filters, str)
    assert "optimizer" in settings3.filters
    assert "adam" in settings3.filters
    assert "accuracy" in settings3.filters

    # Test with list of FilterExpr (gets converted to string internally)
    settings4 = ws.RunsetSettings(
        filters=[wandb_workspaces.expr.Config("learning_rate") == 0.001]
    )
    assert isinstance(settings4.filters, str)
    assert "learning_rate" in settings4.filters
    assert "0.001" in settings4.filters

    # Test empty string
    settings5 = ws.RunsetSettings(filters="")
    assert settings5.filters == ""

    # Test default (no filters)
    settings6 = ws.RunsetSettings()
    assert settings6.filters == ""


def test_workspace_operator_mapping():
    """Test that < maps to <= and > maps to >= in workspace filters."""
    from wandb_workspaces.reports.v2.expr_parsing import expr_to_filters
    import wandb_workspaces.expr as expr
    import warnings

    # Test string filters with < and >
    # For string filters, no warning occurs during RunsetSettings creation
    # (it's just storing the string), but warning occurs when filter is parsed
    settings1 = ws.RunsetSettings(filters="Config('learning_rate') < 0.01")
    with pytest.warns(UserWarning, match="'<' operator.*mapped to '<='"):
        parsed1 = expr_to_filters(settings1.filters)
    assert parsed1.filters[0].filters[0].op == "<="

    settings2 = ws.RunsetSettings(filters="SummaryMetric('accuracy') > 0.95")
    with pytest.warns(UserWarning, match="'>' operator.*mapped to '>='"):
        parsed2 = expr_to_filters(settings2.filters)
    assert parsed2.filters[0].filters[0].op == ">="

    # Test FilterExpr list with < and >
    with pytest.warns(UserWarning):
        settings3 = ws.RunsetSettings(
            filters=[
                expr.Config("learning_rate") < 0.01,
                expr.Summary("accuracy") > 0.95,
            ]
        )
    # After conversion to string, no more warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")
        parsed3 = expr_to_filters(settings3.filters)
        assert parsed3.filters[0].filters[0].op == "<="
        assert parsed3.filters[0].filters[1].op == ">="
        # Filter to only our operator mapping warnings
        operator_warnings = [
            w
            for w in warning_list
            if "operator" in str(w.message) and "mapped to" in str(w.message)
        ]
        assert len(operator_warnings) == 0

    # Test that = and == both work without warnings
    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")
        settings4 = ws.RunsetSettings(filters="Config('optimizer') = 'adam'")
        parsed4 = expr_to_filters(settings4.filters)
        assert parsed4.filters[0].filters[0].op == "="
        # Filter to only our operator mapping warnings
        operator_warnings = [
            w
            for w in warning_list
            if "operator" in str(w.message) and "mapped to" in str(w.message)
        ]
        assert len(operator_warnings) == 0

    with warnings.catch_warnings(record=True) as warning_list:
        warnings.simplefilter("always")
        settings5 = ws.RunsetSettings(filters="Config('optimizer') == 'adam'")
        parsed5 = expr_to_filters(settings5.filters)
        assert parsed5.filters[0].filters[0].op == "="
        # Filter to only our operator mapping warnings
        operator_warnings = [
            w
            for w in warning_list
            if "operator" in str(w.message) and "mapped to" in str(w.message)
        ]
        assert len(operator_warnings) == 0

    # Test combined operators
    settings6 = ws.RunsetSettings(
        filters="Config('lr') < 0.01 and SummaryMetric('acc') > 0.9 and Metric('State') = 'finished'"
    )
    with pytest.warns(UserWarning, match="'<' and/or '>' operators"):
        parsed6 = expr_to_filters(settings6.filters)
    assert parsed6.filters[0].filters[0].op == "<="
    assert parsed6.filters[0].filters[1].op == ">="
    assert parsed6.filters[0].filters[2].op == "="


def test_workspace_string_filters_summary_alias():
    """Test that workspace string filters work with both SummaryMetric (old) and Summary (new) aliases"""
    from wandb_workspaces.reports.v2.expr_parsing import expr_to_filters

    # Test SummaryMetric (old name) in workspace
    settings1 = ws.RunsetSettings(filters="SummaryMetric('loss') <= 0.5")
    parsed1 = expr_to_filters(settings1.filters)
    assert parsed1.filters[0].filters[0].key.section == "summary"
    assert parsed1.filters[0].filters[0].key.name == "loss"
    assert parsed1.filters[0].filters[0].op == "<="
    assert parsed1.filters[0].filters[0].value == 0.5

    # Test Summary (new alias) in workspace
    settings2 = ws.RunsetSettings(filters="Summary('loss') <= 0.5")
    parsed2 = expr_to_filters(settings2.filters)
    assert parsed2.filters[0].filters[0].key.section == "summary"
    assert parsed2.filters[0].filters[0].key.name == "loss"
    assert parsed2.filters[0].filters[0].op == "<="
    assert parsed2.filters[0].filters[0].value == 0.5

    # Test mixed usage in workspace
    settings3 = ws.RunsetSettings(
        filters="SummaryMetric('loss') <= 0.5 and Summary('accuracy') >= 0.85"
    )
    parsed3 = expr_to_filters(settings3.filters)
    assert len(parsed3.filters[0].filters) == 2
    assert parsed3.filters[0].filters[0].key.section == "summary"
    assert parsed3.filters[0].filters[0].key.name == "loss"
    assert parsed3.filters[0].filters[0].op == "<="
    assert parsed3.filters[0].filters[1].key.section == "summary"
    assert parsed3.filters[0].filters[1].key.name == "accuracy"
    assert parsed3.filters[0].filters[1].op == ">="

    # Test in full Workspace object
    workspace = ws.Workspace(
        entity="test",
        project="test",
        name="Test Workspace",
        runset_settings=ws.RunsetSettings(
            filters="SummaryMetric('loss') <= 0.3 and Summary('val_loss') <= 0.4"
        ),
    )
    assert (
        "SummaryMetric" in workspace.runset_settings.filters
        or "Summary" in workspace.runset_settings.filters
    )
    parsed_ws = expr_to_filters(workspace.runset_settings.filters)
    assert len(parsed_ws.filters[0].filters) == 2
    assert parsed_ws.filters[0].filters[0].key.section == "summary"
    assert parsed_ws.filters[0].filters[1].key.section == "summary"


def test_section_pinning():
    """Test that section pinning is properly preserved through serialization."""
    # Create sections with different pinning states
    pinned_section = ws.Section(
        name="Pinned Section",
        panels=[wr.LinePlot(x="Step", y=["loss"])],
        pinned=True,
    )

    unpinned_section = ws.Section(
        name="Unpinned Section",
        panels=[wr.LinePlot(x="Step", y=["accuracy"])],
        pinned=False,
    )

    # Test that pinned=True is preserved
    pinned_model = pinned_section._to_model()
    assert pinned_model.pinned is True

    pinned_roundtrip = ws.Section._from_model(pinned_model)
    assert pinned_roundtrip.pinned is True
    assert pinned_roundtrip.name == "Pinned Section"

    # Test that pinned=False is preserved
    unpinned_model = unpinned_section._to_model()
    assert unpinned_model.pinned is False

    unpinned_roundtrip = ws.Section._from_model(unpinned_model)
    assert unpinned_roundtrip.pinned is False
    assert unpinned_roundtrip.name == "Unpinned Section"

    # Test that sections with pinned=None default to False
    model_with_none = _wr.PanelBankConfigSectionsItem(
        name="Test Section",
        panels=[],
        pinned=None,
    )
    section_from_none = ws.Section._from_model(model_with_none)
    assert section_from_none.pinned is False


def test_load_workspace_from_url():
    url = "https://app.wandb.test/test_entity/test_project?nw=51cset95tvn"

    mock_response = {
        "project": {
            "allViews": {
                "edges": [
                    {
                        "node": {
                            "id": "VmlldzoxMzcwNzMyNg==",
                            "displayName": "Updated Workspace Name",
                            "spec": '{"section":{"panelBankConfig":{"state":1,"settings":{"autoOrganizePrefix":2,"showEmptySections":false,"sortAlphabetically":false},"sections":[{"name":"Charts","isOpen":true,"type":"flow","flowConfig":{"snapToColumns":true,"columnsPerPage":3,"rowsPerPage":2,"gutterWidth":16,"boxWidth":460,"boxHeight":300},"sorted":0,"localPanelSettings":{"smoothingWeight":0,"smoothingType":"exponential","xAxis":"_step","ignoreOutliers":false,"useRunsTableGroupingInPanels":true,"smoothingActive":true,"xAxisActive":false},"panels":[]},{"name":"Hidden Panels","isOpen":false,"type":"flow","flowConfig":{"snapToColumns":true,"columnsPerPage":3,"rowsPerPage":2,"gutterWidth":16,"boxWidth":460,"boxHeight":300},"sorted":0,"localPanelSettings":{"smoothingWeight":0,"smoothingType":"exponential","xAxis":"_step","ignoreOutliers":false,"useRunsTableGroupingInPanels":true,"smoothingActive":true,"xAxisActive":false},"panels":[]}]},"panelBankSectionConfig":{"name":"Report Panels","isOpen":false,"panels":[],"type":"grid","flowConfig":{"snapToColumns":true,"columnsPerPage":3,"rowsPerPage":2,"gutterWidth":16,"boxWidth":460,"boxHeight":300},"sorted":0,"localPanelSettings":{"smoothingWeight":0,"smoothingType":"exponential","xAxis":"_step","ignoreOutliers":false,"useRunsTableGroupingInPanels":true,"smoothingActive":true,"xAxisActive":false},"pinned":false},"customRunColors":{},"name":"","runSets":[{"id":"yprlbpw0q","runFeed":{"version":2,"columnVisible":{"run:name":false},"columnPinned":{},"columnWidths":{},"columnOrder":[],"pageSize":10,"onlyShowSelected":false},"enabled":true,"name":"Run set","search":{"query":""},"filters":{"op":"OR","filters":[{"op":"AND","filters":[]}]},"grouping":[],"sort":{"keys":[{"key":{"section":"run","name":"createdAt"},"ascending":false}]},"selections":{"root":1,"bounds":[],"tree":[]},"expandedRowAddresses":[]}],"settings":{"smoothingWeight":0,"smoothingType":"exponential","xAxis":"_step","ignoreOutliers":false,"useRunsTableGroupingInPanels":true,"maxRuns":10,"pointVisualizationMethod":"bucketing-gorilla","tooltipNumberOfRuns":"default","shouldAutoGeneratePanels":false,"smoothingActive":true,"xAxisActive":false},"openRunSet":0,"openViz":true},"vizExpanded":false,"libraryExpanded":true}',
                        }
                    }
                ]
            }
        }
    }

    mock_api_instance, mock_client = create_mock_wandb_api(mock_response)

    with patch("wandb.Api", return_value=mock_api_instance):
        workspace = ws.Workspace.from_url(url)
        assert len(workspace.sections) == 2
        assert workspace.sections[0].name == "Charts"
        assert workspace.sections[1].name == "Hidden Panels"

        # Verify the mock was called
        assert mock_client.execute.call_count == 1
        cargs = mock_client.execute.call_args[0]
        gql_definition = cargs[0].definitions[0]
        assert gql_definition.name.value == "View"
        assert gql_definition.operation == "query"
        assert cargs[1] == {
            "viewType": "project-view",
            "entityName": "test_entity",
            "projectName": "test_project",
            "name": "test_project",
            "viewName": "nw-51cset95tvn-v",
        }


def test_save_workspace():
    mock_upsert_response = {
        "upsertView": {
            "view": {"id": "test-view-id-123", "name": "nw-firstworkspace-v"},
            "inserted": True,
        }
    }

    mock_api_instance, mock_client = create_mock_wandb_api(mock_upsert_response)

    with patch("wandb.Api", return_value=mock_api_instance):
        workspace = ws.Workspace(entity="test", project="test")
        workspace.save()
        workspace.save()
        workspace.save_as_new_view()

        assert mock_client.execute.call_count == 3
        cargs_list = mock_client.execute.call_args_list

        # Important: id SHOULD not be in the first call as view hasn't been created
        assert "id" not in cargs_list[0][0][1]

        # Important: id SHOULD be in the second call as the view has been created
        assert "id" in cargs_list[1][0][1]

        # Important: id SHOULD not be in the third call as we want to make a new view
        assert "id" not in cargs_list[2][0][1]

        # all the gql should be the same
        assert cargs_list[0][0][0] == cargs_list[1][0][0]
        assert cargs_list[1][0][0] == cargs_list[2][0][0]
        gql_definition = cargs_list[0][0][0].definitions[0]
        assert gql_definition.name.value == "UpsertView2"
        assert gql_definition.operation == "mutation"


@pytest.mark.parametrize(
    "example, should_pass",
    [
        ("abc", True),
        ("вэбэ", True),
        ("汉字", True),
        ("漢字", True),
        ("𡨸漢", True),
        ("한자", True),
        ("漢字", True),
        ("한글", True),
        ("😀", False),
        ("wow😀zers", False),
    ],
)
def test_validate_no_emoji(example, should_pass):
    if should_pass:
        validate_no_emoji(example)
    else:
        with pytest.raises(ValueError):
            validate_no_emoji(example)


@pytest.mark.parametrize(
    "example, should_pass",
    [
        ({}, False),  # No version
        ({"version": 4}, False),  # Lower version
        ({"version": 5}, True),  # Expected version
        ({"version": 6}, False),  # Higher version
    ],
)
def test_validate_spec_version(example, should_pass):
    expected_ver = 5
    if should_pass:
        validate_spec_version(example, expected_version=expected_ver)
    else:
        with pytest.raises(SpecVersionError):
            validate_spec_version(example, expected_version=expected_ver)


@pytest.mark.parametrize(
    "example, should_pass",
    [
        (
            # saved view url
            "https://wandb.ai/entity/project?nw=ejh7s85g63o",
            True,
        ),
        (
            # username url
            "https://wandb.ai/entity/project?nw=nwusermegatruong",
            False,
        ),
        (
            # sweeps url
            "https://wandb.ai/entity/project/sweeps/lqo1hrfk?nw=5ck3t077hir",
            False,
        ),
        (
            # singular run url
            "https://wandb.ai/entity/project/runs/1mbku38n?nw=1f8jocblz8z",
            False,
        ),
    ],
)
def test_validate_url(example, should_pass):
    if should_pass:
        validate_url(example)
    else:
        with pytest.raises(UnsupportedViewError):
            validate_url(example)


@pytest.mark.parametrize(
    "panel_config, should_return_instance",
    [
        (
            WeavePanelFactory.build_summary_table_panel(),
            wr.interface.WeavePanelSummaryTable,
        ),
        (WeavePanelFactory.build_artifact_panel(), wr.interface.WeavePanelArtifact),
        (
            WeavePanelFactory.build_artifact_version_panel(),
            wr.interface.WeavePanelArtifactVersionedFile,
        ),
        (WeavePanelFactory.build_run_var_panel(), wr.interface.WeavePanel),
        (_wr.UnknownPanel(), wr.interface.UnknownPanel),
    ],
)
def test_panel_lookup(panel_config, should_return_instance):
    panel = wr.interface._lookup_panel(panel_config)
    assert isinstance(panel, should_return_instance)


# Column Management Tests


def test_column_pinning():
    """Test that column pinning is preserved through serialization."""
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(
            pinned_columns=["summary:accuracy"],  # run:displayName auto-added
        ),
    )
    model = workspace._to_model()

    # Backend should receive dict format with True values
    # run:displayName should be auto-added
    assert model.spec.section.run_sets[0].run_feed.column_pinned == {
        "run:displayName": True,
        "summary:accuracy": True,
    }

    # column_visible should match column_pinned (pinned columns are the only visible ones)
    assert model.spec.section.run_sets[0].run_feed.column_visible == {
        "run:displayName": True,
        "summary:accuracy": True,
    }

    # column_order should also match
    assert model.spec.section.run_sets[0].run_feed.column_order == [
        "run:displayName",
        "summary:accuracy",
    ]

    # Test round-trip - should convert back to list format
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_columns == [
        "run:displayName",
        "summary:accuracy",
    ]


def test_empty_column_settings():
    """Test that empty column settings are handled correctly."""
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(),
    )

    model = workspace._to_model()
    run_feed = model.spec.section.run_sets[0].run_feed

    # Verify empty settings serialize correctly
    assert run_feed.column_pinned == {}
    assert run_feed.column_visible == {}
    assert run_feed.column_order == []

    # Test round-trip - should be empty list
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_columns == []


def test_run_display_name_auto_added_to_pinned():
    """Test that 'run:displayName' is automatically added to pinned_columns if missing."""
    # This should work without errors - run:displayName is auto-added in validation
    runset_settings = ws.RunsetSettings(
        pinned_columns=[
            "summary:accuracy"
        ],  # missing run:displayName - will be auto-added
    )
    # run:displayName is added and moved to first position during validation
    assert runset_settings.pinned_columns == ["run:displayName", "summary:accuracy"]
