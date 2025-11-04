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
                "op": ">",
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


@patch("wandb_workspaces.workspaces.internal.fetch_project_fields")
def test_column_pinning(mock_fetch):
    """Test that column pinning is preserved through serialization."""
    # Mock fetch_project_fields to return a known set of fields
    mock_fetch.return_value = [
        "run:displayName",
        "summary:accuracy",
        "summary:loss",
    ]

    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(
            pinned_columns=["run:displayName", "summary:accuracy"],
            visible_columns=["run:displayName", "summary:accuracy", "summary:loss"],
            column_order=["run:displayName", "summary:accuracy", "summary:loss"],
        ),
    )
    model = workspace._to_model()
    # Backend should receive dict format with True values
    assert model.spec.section.run_sets[0].run_feed.column_pinned == {
        "run:displayName": True,
        "summary:accuracy": True,
    }

    # Test round-trip - should convert back to list format
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_columns == [
        "run:displayName",
        "summary:accuracy",
    ]


@patch("wandb_workspaces.workspaces.internal.fetch_project_fields")
def test_column_visibility(mock_fetch):
    """Test that column visibility is preserved."""
    # Mock fetch_project_fields to return a known set of fields
    mock_fetch.return_value = [
        "run:displayName",
        "summary:loss",
        "config:learning_rate",
    ]

    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(
            visible_columns=["run:displayName", "summary:loss", "config:learning_rate"]
        ),
    )
    model = workspace._to_model()
    # Backend should receive dict format
    assert model.spec.section.run_sets[0].run_feed.column_visible == {
        "run:displayName": True,
        "summary:loss": True,
        "config:learning_rate": True,
    }

    # Test round-trip - should convert back to list format
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.visible_columns == [
        "run:displayName",
        "summary:loss",
        "config:learning_rate",
    ]


def test_column_ordering():
    """Test that column order is preserved."""
    order = ["run:displayName", "summary:accuracy", "summary:loss"]
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(column_order=order),
    )
    model = workspace._to_model()
    assert model.spec.section.run_sets[0].run_feed.column_order == order

    # Test round-trip
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.column_order == order


def test_column_widths():
    """Test that column widths are preserved."""
    widths = {"run:displayName": 200, "summary:accuracy": 150}
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(column_widths=widths),
    )
    model = workspace._to_model()
    assert model.spec.section.run_sets[0].run_feed.column_widths == widths

    # Test round-trip
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.column_widths == widths


def test_column_width_minimum_enforced():
    """Test that column widths must be at least 70px."""
    with pytest.raises(
        ValueError,
        match="Column width for 'summary:accuracy' is 50px, but minimum width is 70px",
    ):
        ws.RunsetSettings(
            column_widths={
                "run:displayName": 200,
                "summary:accuracy": 50,
            }  # Too narrow!
        )


def test_column_width_at_minimum_allowed():
    """Test that column width of exactly 70px is allowed."""
    # This should work without errors
    runset_settings = ws.RunsetSettings(
        column_widths={"run:displayName": 70, "summary:accuracy": 70}
    )
    assert runset_settings.column_widths["run:displayName"] == 70
    assert runset_settings.column_widths["summary:accuracy"] == 70


def test_column_width_below_minimum_fails():
    """Test that column width below 70px fails."""
    with pytest.raises(
        ValueError,
        match="Column width for 'run:displayName' is 69px, but minimum width is 70px",
    ):
        ws.RunsetSettings(column_widths={"run:displayName": 69})


@patch("wandb_workspaces.workspaces.internal.fetch_project_fields")
def test_all_column_management_features(mock_fetch):
    """Test that all column management features work together."""
    # Mock fetch_project_fields to return a known set of fields
    mock_fetch.return_value = [
        "run:displayName",
        "run:state",
        "summary:accuracy",
        "config:learning_rate",
    ]

    pinned_cols = ["run:displayName", "run:state"]
    visible_cols = [
        "run:displayName",
        "run:state",
        "summary:accuracy",
        "config:learning_rate",
    ]
    col_order = [
        "run:displayName",
        "run:state",
        "summary:accuracy",
        "config:learning_rate",
    ]
    col_widths = {
        "run:displayName": 250,
        "summary:accuracy": 120,
    }

    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(
            pinned_columns=pinned_cols,
            visible_columns=visible_cols,
            column_order=col_order,
            column_widths=col_widths,
        ),
    )

    model = workspace._to_model()
    run_feed = model.spec.section.run_sets[0].run_feed

    # Verify serialization - backend should receive dict format
    assert run_feed.column_pinned == {
        "run:displayName": True,
        "run:state": True,
    }
    assert run_feed.column_visible == {
        "run:displayName": True,
        "run:state": True,
        "summary:accuracy": True,
        "config:learning_rate": True,
    }
    assert run_feed.column_order == col_order
    assert run_feed.column_widths == col_widths

    # Test round-trip - should convert back to list format
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_columns == pinned_cols
    assert workspace2.runset_settings.visible_columns == visible_cols
    assert workspace2.runset_settings.column_order == col_order
    assert workspace2.runset_settings.column_widths == col_widths


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
    assert run_feed.column_widths == {}

    # Test round-trip - should be empty lists
    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_columns == []
    assert workspace2.runset_settings.visible_columns == []
    assert workspace2.runset_settings.column_order == []
    assert workspace2.runset_settings.column_widths == {}


def test_pinned_columns_requires_visible_columns():
    """Test that pinned_columns requires visible_columns to be populated."""
    with pytest.raises(ValueError, match="visible_columns must also be provided"):
        ws.RunsetSettings(
            pinned_columns=["run:displayName"],
            column_order=["run:displayName"],
        )


def test_pinned_columns_allows_empty_column_order():
    """Test that pinned_columns allows empty column_order (it will be populated in Workspace.__post_init__())."""
    # This should work - empty column_order is OK
    runset_settings = ws.RunsetSettings(
        pinned_columns=["run:displayName"],
        visible_columns=["run:displayName"],
        column_order=[],  # Empty is allowed
    )
    assert runset_settings.pinned_columns == ["run:displayName"]
    assert (
        runset_settings.column_order == []
    )  # Will be populated by Workspace.__post_init__()


def test_pinned_columns_requires_both():
    """Test that pinned_columns requires both visible_columns and column_order."""
    with pytest.raises(ValueError, match="visible_columns must also be provided"):
        ws.RunsetSettings(
            pinned_columns=["run:displayName"],
        )


def test_all_column_settings_together_valid():
    """Test that all column settings can be used together without error."""
    # This should not raise an error
    runset_settings = ws.RunsetSettings(
        pinned_columns=["run:displayName"],
        visible_columns=["run:displayName", "summary:accuracy"],
        column_order=["run:displayName", "summary:accuracy"],
    )
    assert runset_settings.pinned_columns == ["run:displayName"]
    assert runset_settings.visible_columns == ["run:displayName", "summary:accuracy"]
    assert runset_settings.column_order == ["run:displayName", "summary:accuracy"]


def test_pinned_column_must_be_in_visible_columns():
    """Test that pinned columns must be in visible_columns."""
    with pytest.raises(
        ValueError, match="Missing from visible_columns: \\['summary:accuracy'\\]"
    ):
        ws.RunsetSettings(
            pinned_columns=["run:displayName", "summary:accuracy"],
            visible_columns=["run:displayName"],  # missing summary:accuracy
            column_order=["run:displayName", "summary:accuracy"],
        )


def test_pinned_column_must_be_in_column_order():
    """Test that pinned columns must be in column_order."""
    with pytest.raises(
        ValueError, match="Missing from column_order: \\['summary:accuracy'\\]"
    ):
        ws.RunsetSettings(
            pinned_columns=["run:displayName", "summary:accuracy"],
            visible_columns=["run:displayName", "summary:accuracy"],
            column_order=["run:displayName"],  # missing summary:accuracy
        )


def test_run_display_name_auto_added_to_pinned():
    """Test that 'run:displayName' is automatically added to pinned_columns if missing."""
    # This should work without errors - run:displayName is auto-added
    runset_settings = ws.RunsetSettings(
        pinned_columns=[
            "summary:accuracy"
        ],  # missing run:displayName - will be auto-added
        visible_columns=["summary:accuracy"],
        column_order=["summary:accuracy"],
    )
    # At this point, validation has passed, but run:displayName hasn't been added yet
    # It's added in Workspace.__post_init__()
    assert runset_settings.pinned_columns == ["summary:accuracy"]


def test_run_display_name_can_be_out_of_order():
    """Test that 'run:displayName' order is automatically fixed in Workspace.__post_init__()."""
    # This should work without errors - run:displayName order is auto-fixed
    runset_settings = ws.RunsetSettings(
        pinned_columns=["run:displayName", "summary:accuracy"],
        visible_columns=["run:displayName", "summary:accuracy"],
        column_order=[
            "summary:accuracy",
            "run:displayName",
        ],  # Wrong order - will be auto-fixed
    )
    # At this point validation has passed
    # run:displayName order is fixed in Workspace.__post_init__()
    assert "run:displayName" in runset_settings.pinned_columns


def test_fetch_project_fields_basic():
    """Test that fetch_project_fields returns correctly formatted field names."""
    from wandb_workspaces.workspaces import internal

    # Mock the GraphQL response using actual dev server response structure
    mock_response = {
        "data": {
            "project": {
                "id": "UHJvamVjdDp2MTpncm91cGVkOmFjYXNleS1kZXY=",
                "fields": {
                    "pageInfo": {
                        "hasNextPage": False,
                        "endCursor": "YXJyYXljb25uZWN0aW9uOjEy",
                        "__typename": "PageInfo",
                    },
                    "edges": [
                        {
                            "node": {
                                "path": "config.architecture.value",
                                "type": "string",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "config.dataset.value",
                                "type": "string",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "config.epochs.value",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "config.learning_rate.value",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "summary_metrics._runtime",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "summary_metrics._step",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "summary_metrics._timestamp",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "summary_metrics.acc",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "summary_metrics.loss",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "aggregations_min.acc",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "aggregations_max.acc",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "aggregations_min.loss",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                        {
                            "node": {
                                "path": "aggregations_max.loss",
                                "type": "number",
                                "__typename": "ProjectField",
                            },
                            "__typename": "ProjectFieldEdge",
                        },
                    ],
                    "__typename": "ProjectFieldConnection",
                },
                "__typename": "Project",
            }
        }
    }

    # Setup mock to return our response
    with patch("wandb.Api") as mock_api:
        mock_client = Mock()
        mock_client.execute.return_value = mock_response
        mock_api.return_value.client = mock_client

        fields = internal.fetch_project_fields("test-entity", "test-project")

        # Should include standard run columns
        assert "run:displayName" in fields
        assert "run:state" in fields
        assert "tags:__ALL__" in fields

        # Should transform backend format to workspace SDK format
        # Config fields already have .value suffix in backend response
        assert "config:architecture.value" in fields
        assert "config:dataset.value" in fields
        assert "config:epochs.value" in fields
        assert "config:learning_rate.value" in fields

        # Summary metrics
        assert "summary:_runtime" in fields
        assert "summary:_step" in fields
        assert "summary:_timestamp" in fields
        assert "summary:acc" in fields
        assert "summary:loss" in fields

        # Aggregation fields
        assert "aggregations_min:acc" in fields
        assert "aggregations_max:acc" in fields
        assert "aggregations_min:loss" in fields
        assert "aggregations_max:loss" in fields


@patch("wandb_workspaces.workspaces.internal.fetch_project_fields")
def test_auto_hide_others_basic(mock_fetch):
    """Test that specifying columns automatically hides all others (default behavior)."""
    # Mock fetch_project_fields to return a known set of fields
    mock_fetch.return_value = [
        "run:displayName",
        "run:state",
        "run:createdAt",
        "summary:loss",
        "summary:accuracy",
        "config:learning_rate.value",
        "tags:__ALL__",
    ]

    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        name="Test Auto Hide",
        runset_settings=ws.RunsetSettings(
            pinned_columns=["run:displayName", "summary:loss"],
            visible_columns=["run:displayName", "summary:loss"],
            column_order=["run:displayName", "summary:loss"],
        ),
    )

    # Check that _visible_columns_dict was created with all fields
    assert hasattr(workspace, "_visible_columns_dict")
    assert "run:displayName" in workspace._visible_columns_dict
    assert "summary:loss" in workspace._visible_columns_dict
    assert "summary:accuracy" in workspace._visible_columns_dict
    assert "config:learning_rate.value" in workspace._visible_columns_dict

    # Check that specified columns are True
    assert workspace._visible_columns_dict["run:displayName"] is True
    assert workspace._visible_columns_dict["summary:loss"] is True

    # Check that other columns are False
    assert workspace._visible_columns_dict["summary:accuracy"] is False
    assert workspace._visible_columns_dict["config:learning_rate.value"] is False
    assert workspace._visible_columns_dict["run:state"] is False


@patch("wandb_workspaces.workspaces.internal.fetch_project_fields")
def test_auto_hide_others_ensures_run_display_name(mock_fetch):
    """Test that column specification ensures run:displayName is always pinned and first."""
    mock_fetch.return_value = [
        "run:displayName",
        "run:state",
        "summary:loss",
        "summary:accuracy",
    ]

    # Don't explicitly include run:displayName in pinned_columns
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        name="Test Auto Hide",
        runset_settings=ws.RunsetSettings(
            pinned_columns=["summary:loss"],
            visible_columns=["summary:loss"],
            column_order=["summary:loss"],
        ),
    )

    # Should automatically add run:displayName to pinned_columns
    assert "run:displayName" in workspace.runset_settings.pinned_columns
    assert workspace.runset_settings.pinned_columns[0] == "run:displayName"

    # Should be in visible columns
    assert "run:displayName" in workspace._visible_columns_dict
    assert workspace._visible_columns_dict["run:displayName"] is True

    # Should be first in column_order
    assert workspace.runset_settings.column_order[0] == "run:displayName"


@patch("wandb_workspaces.workspaces.internal.fetch_project_fields")
def test_auto_hide_others_preserves_explicit_visible_columns(mock_fetch):
    """Test that column specification preserves explicitly set visible_columns."""
    mock_fetch.return_value = [
        "run:displayName",
        "summary:loss",
        "summary:accuracy",
        "summary:f1",
    ]

    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        name="Test Auto Hide",
        runset_settings=ws.RunsetSettings(
            pinned_columns=["run:displayName", "summary:loss"],
            visible_columns=[
                "run:displayName",
                "summary:loss",
                "summary:accuracy",  # Explicitly set to visible, not pinned
            ],
            column_order=["run:displayName", "summary:loss"],
        ),
    )

    # Pinned columns should be True in the internal dict
    assert workspace._visible_columns_dict["run:displayName"] is True
    assert workspace._visible_columns_dict["summary:loss"] is True

    # Explicitly set visible column should be True
    assert workspace._visible_columns_dict["summary:accuracy"] is True

    # Other columns should be False
    assert workspace._visible_columns_dict["summary:f1"] is False


@patch("wandb_workspaces.workspaces.internal.fetch_project_fields")
def test_auto_hide_others_with_empty_column_order(mock_fetch):
    """Test that column specification creates column_order if it's empty."""
    mock_fetch.return_value = [
        "run:displayName",
        "run:state",
        "summary:loss",
        "summary:accuracy",
    ]

    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        name="Test Auto Hide",
        runset_settings=ws.RunsetSettings(
            pinned_columns=["run:displayName", "summary:loss"],
            visible_columns=["run:displayName", "summary:loss"],
            column_order=[],  # Empty
        ),
    )

    # Should create column_order with run:displayName first
    assert len(workspace.runset_settings.column_order) > 0
    assert workspace.runset_settings.column_order[0] == "run:displayName"
    assert "summary:loss" in workspace.runset_settings.column_order
