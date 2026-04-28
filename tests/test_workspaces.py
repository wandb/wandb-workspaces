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


def test_workspace_viewspec_preserves_frontend_owned_fields():
    """Workspace parsing should not drop current frontend-owned spec fields."""
    from wandb_workspaces.workspaces import internal

    spec = internal.WorkspaceViewspec.model_validate(
        {
            "section": {
                "version": 9,
                "panelBankConfig": {"state": 1, "settings": {}, "sections": []},
                "panelBankSectionConfig": {},
                "customRunColors": {},
                "customRunNames": {"run-a": "Best Run"},
                "workspaceSettings": {
                    "linePlot": {"showLegend": False},
                    "media": {"maxRuns": 5},
                },
                "semanticLegendSettings": {
                    "runColorOptions": "semantic-legend",
                    "excludedRunColor": "#cccccc",
                },
                "settings": {"shouldAutoGeneratePanels": "pending"},
                "runSets": [{"id": "rs1"}],
            },
            "vizExpanded": True,
            "libraryExpanded": False,
            "slowWarningHiddenAt": "2026-01-01T00:00:00Z",
        }
    )

    dumped = spec.model_dump(by_alias=True, exclude_none=True)
    assert dumped["section"]["version"] == 9
    assert dumped["section"]["customRunNames"] == {"run-a": "Best Run"}
    assert dumped["section"]["workspaceSettings"]["linePlot"]["showLegend"] is False
    assert dumped["section"]["workspaceSettings"]["media"]["maxRuns"] == 5
    assert (
        dumped["section"]["semanticLegendSettings"]["runColorOptions"]
        == "semantic-legend"
    )
    assert dumped["section"]["settings"]["shouldAutoGeneratePanels"] == "pending"
    assert dumped["slowWarningHiddenAt"] == "2026-01-01T00:00:00Z"


def test_panel_bank_sparse_overrides_validate_and_round_trip():
    """Current frontend sparse override fields are structured objects, not colors."""
    model = _wr.PanelBankConfig.model_validate(
        {
            "state": 1,
            "settings": {},
            "sections": [],
            "panelPlacementOverrides": {
                "loss": {"sectionId": "section-1", "orderKey": "a0"}
            },
            "panelConfigOverrides": {
                "loss": {
                    "config": {"chartTitle": "Loss"},
                    "layout": {"w": 8},
                }
            },
        }
    )

    dumped = model.model_dump(by_alias=True, exclude_none=True)
    assert dumped["panelPlacementOverrides"] == {
        "loss": {"sectionId": "section-1", "orderKey": "a0"}
    }
    assert dumped["panelConfigOverrides"] == {
        "loss": {"config": {"chartTitle": "Loss"}, "layout": {"w": 8}}
    }


def test_loaded_workspace_round_trip_preserves_frontend_state():
    """Saving a loaded workspace should preserve fields the SDK does not expose."""
    from wandb_workspaces.workspaces import internal

    spec = internal.WorkspaceViewspec.model_validate(
        {
            "section": {
                "name": "Original Wrapper",
                "version": 9,
                "panelBankConfig": {
                    "state": 1,
                    "settings": {
                        "autoOrganizePrefix": 1,
                        "showEmptySections": True,
                        "sortAlphabetically": True,
                        "searchQuery": "loss",
                    },
                    "panelPlacementOverrides": {
                        "loss": {"sectionId": "section-1", "orderKey": "a0"}
                    },
                    "sections": [
                        {
                            "__id__": "section-1",
                            "defaultName": "Charts",
                            "name": "Charts",
                            "isOpen": True,
                            "type": "flow",
                            "flowConfig": {
                                "snapToColumns": False,
                                "columnsPerPage": 4,
                                "rowsPerPage": 5,
                                "gutterWidth": 24,
                                "boxWidth": 500,
                                "boxHeight": 320,
                                "mobileColumnsPerPage": 1,
                            },
                            "sorted": 1,
                            "localPanelSettings": {
                                "smoothingWeight": 9,
                                "smoothingType": "gaussian",
                                "xAxis": "_runtime",
                                "ignoreOutliers": True,
                            },
                            "sectionSettings": {"linePlot": {"showLegend": False}},
                            "panels": [],
                            "pinned": True,
                        }
                    ],
                },
                "panelBankSectionConfig": {"pinned": False},
                "customRunColors": {"run-a": "#ff0000"},
                "customRunNames": {"run-a": "Best Run"},
                "workspaceSettings": {
                    "linePlot": {"showLegend": False},
                    "media": {"maxRuns": 5},
                },
                "semanticLegendSettings": {
                    "runColorOptions": "semantic-legend",
                    "excludedRunColor": "#cccccc",
                },
                "runSets": [
                    {
                        "id": "rs1",
                        "enabled": False,
                        "runFeed": {
                            "version": 2,
                            "columnVisible": {"run:name": True, "config:lr": True},
                            "columnPinned": {
                                "run:displayName": True,
                                "config:lr": True,
                            },
                            "columnWidths": {"run:name": 222},
                            "columnOrder": [
                                "run:displayName",
                                "config:lr",
                                "summary:loss",
                            ],
                            "pageSize": 50,
                            "onlyShowSelected": True,
                        },
                        "search": {"query": "abc", "isRegex": True},
                        "filters": {"op": "OR", "filters": [{"op": "AND"}]},
                        "grouping": [],
                        "sort": {
                            "keys": [
                                {
                                    "key": {
                                        "section": "run",
                                        "name": "createdAt",
                                    },
                                    "ascending": False,
                                }
                            ]
                        },
                        "selections": {
                            "root": 1,
                            "bounds": [
                                {"key": {"section": "run", "name": "createdAt"}}
                            ],
                            "tree": ["run-b"],
                        },
                        "expandedRowAddresses": ["0/run-b"],
                    }
                ],
                "settings": {
                    "xAxis": "_runtime",
                    "xAxisMin": 1,
                    "xAxisMax": 9,
                    "smoothingType": "gaussian",
                    "smoothingWeight": 4,
                    "ignoreOutliers": True,
                    "shouldAutoGeneratePanels": "pending",
                },
                "openRunSet": 3,
                "openViz": False,
            },
            "vizExpanded": True,
            "libraryExpanded": False,
            "slowWarningHiddenAt": "2026-01-01T00:00:00Z",
        }
    )
    view = internal.View(
        entity="test-entity",
        project="test-project",
        display_name="Loaded Workspace",
        name="nw-loaded-v",
        id="view-id",
        spec=spec,
    )

    workspace = ws.Workspace._from_model(view)
    dumped = workspace._to_model().spec.model_dump(by_alias=True, exclude_none=True)
    section = dumped["section"]
    runset = section["runSets"][0]
    run_feed = runset["runFeed"]

    assert dumped["vizExpanded"] is True
    assert dumped["libraryExpanded"] is False
    assert dumped["slowWarningHiddenAt"] == "2026-01-01T00:00:00Z"
    assert section["version"] == 9
    assert section["openRunSet"] == 3
    assert section["openViz"] is False
    assert section["customRunNames"] == {"run-a": "Best Run"}
    assert section["workspaceSettings"]["linePlot"]["showLegend"] is False
    assert section["semanticLegendSettings"]["excludedRunColor"] == "#cccccc"
    assert section["settings"]["shouldAutoGeneratePanels"] == "pending"
    assert section["panelBankConfig"]["settings"]["showEmptySections"] is True
    assert section["panelBankConfig"]["settings"]["searchQuery"] == "loss"
    assert section["panelBankConfig"]["panelPlacementOverrides"] == {
        "loss": {"sectionId": "section-1", "orderKey": "a0"}
    }
    assert (
        section["panelBankConfig"]["sections"][0]["flowConfig"]["snapToColumns"]
        is False
    )
    assert (
        section["panelBankConfig"]["sections"][0]["flowConfig"]["mobileColumnsPerPage"]
        == 1
    )
    assert section["panelBankConfig"]["sections"][0]["sorted"] == 1
    assert section["panelBankConfig"]["sections"][0]["sectionSettings"] == {
        "linePlot": {"showLegend": False}
    }
    assert runset["enabled"] is False
    assert runset["expandedRowAddresses"] == ["0/run-b"]
    assert runset["selections"]["bounds"] == [
        {"key": {"section": "run", "name": "createdAt"}}
    ]
    assert run_feed["columnVisible"] == {"run:name": True, "config:lr": True}
    assert run_feed["columnWidths"] == {"run:name": 222}
    assert run_feed["pageSize"] == 50
    assert run_feed["onlyShowSelected"] is True
    assert section["customRunColors"] == {"run-a": "#ff0000"}


def test_loaded_workspace_preserves_additive_selection_tree():
    """Color-only run settings should not flatten additive grouped selections."""
    from wandb_workspaces.workspaces import internal

    spec = internal.WorkspaceViewspec.model_validate(
        {
            "section": {
                "panelBankConfig": {"state": 1, "settings": {}, "sections": []},
                "panelBankSectionConfig": {},
                "customRunColors": {"run-color": "#00ff00"},
                "runSets": [
                    {
                        "id": "rs1",
                        "selections": {
                            "root": 0,
                            "bounds": [],
                            "tree": [
                                {
                                    "value": "group-a",
                                    "children": ["run-a", "run-b"],
                                    "skip": False,
                                }
                            ],
                        },
                    }
                ],
            }
        }
    )
    view = internal.View(
        entity="test-entity",
        project="test-project",
        display_name="Loaded Workspace",
        name="nw-loaded-v",
        id="view-id",
        spec=spec,
    )

    dumped = (
        ws.Workspace._from_model(view)
        ._to_model()
        .spec.model_dump(by_alias=True, exclude_none=True)
    )
    selections = dumped["section"]["runSets"][0]["selections"]

    assert selections["root"] == 0
    assert selections["tree"] == [
        {
            "value": "group-a",
            "children": ["run-a", "run-b"],
            "skip": False,
        }
    ]
    assert dumped["section"]["customRunColors"] == {"run-color": "#00ff00"}


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


def test_workspace_lineplot_metric_regex():
    """Test LinePlot metric_regex field in workspace sections."""
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        sections=[
            ws.Section(
                name="Training Metrics",
                panels=[
                    wr.LinePlot(
                        title="Train Metrics",
                        metric_regex="train/.*",
                    ),
                ],
            ),
        ],
    )

    # Check field is set correctly
    panel = workspace.sections[0].panels[0]
    assert panel.metric_regex == "train/.*"

    # Test serialization to internal model - use_metric_regex should be auto-set
    model = workspace._to_model()
    panel_config = model.spec.section.panel_bank_config.sections[0].panels[0].config
    assert panel_config.metric_regex == "train/.*"
    assert panel_config.use_metric_regex is True  # Auto-set internally

    # Test round-trip serialization
    workspace2 = ws.Workspace._from_model(model)
    panel2 = workspace2.sections[0].panels[0]
    assert panel2.metric_regex == "train/.*"
