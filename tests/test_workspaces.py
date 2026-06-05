import base64
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
        ckwargs = mock_client.execute.call_args.kwargs
        gql_definition = cargs[0].definitions[0]
        assert gql_definition.name.value == "View"
        assert gql_definition.operation == "query"
        assert ckwargs["variable_values"] == {
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
        assert "id" not in cargs_list[0].kwargs["variable_values"]

        # Important: id SHOULD be in the second call as the view has been created
        assert "id" in cargs_list[1].kwargs["variable_values"]

        # Important: id SHOULD not be in the third call as we want to make a new view
        assert "id" not in cargs_list[2].kwargs["variable_values"]

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


# Baseline / Pinned Runs Tests


def test_baseline_and_pinned_runs_roundtrip():
    """Both baseline_run and pinned_runs round-trip through _to_model /
    _from_model: slugs in, base64-encoded `Run:v1:` GIDs on the wire (the
    format the viewspec stores), slugs back out on read."""
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(
            baseline_run="1mbku38n",
            pinned_runs=["1mbku38n", "2u1g3j1c"],
        ),
    )

    model = workspace._to_model()
    runset = model.spec.section.run_sets[0]

    expected_baseline_gid = base64.b64encode(
        b"Run:v1:1mbku38n:test-project:test-entity"
    ).decode()
    expected_pinned_gids = [
        base64.b64encode(b"Run:v1:1mbku38n:test-project:test-entity").decode(),
        base64.b64encode(b"Run:v1:2u1g3j1c:test-project:test-entity").decode(),
    ]
    assert runset.baseline_run_id == expected_baseline_gid
    assert runset.pinned_run_ids == expected_pinned_gids

    # Verify the camelCase keys land in the dumped spec JSON
    dumped = model.spec.model_dump(by_alias=True, exclude_none=True)
    rs_dump = dumped["section"]["runSets"][0]
    assert rs_dump["baselineRunId"] == expected_baseline_gid
    assert rs_dump["pinnedRunIds"] == expected_pinned_gids

    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.baseline_run == "1mbku38n"
    assert workspace2.runset_settings.pinned_runs == ["1mbku38n", "2u1g3j1c"]


def test_pinned_runs_encoded_with_workspace_project_and_entity():
    """The encoded GID embeds the workspace's own (project, entity), so the
    same slug used in two workspaces produces two different GIDs."""
    ws_a = ws.Workspace(
        entity="entity-a",
        project="project-a",
        runset_settings=ws.RunsetSettings(pinned_runs=["g0dpjzew"]),
    )
    ws_b = ws.Workspace(
        entity="entity-b",
        project="project-b",
        runset_settings=ws.RunsetSettings(pinned_runs=["g0dpjzew"]),
    )

    gid_a = ws_a._to_model().spec.section.run_sets[0].pinned_run_ids[0]
    gid_b = ws_b._to_model().spec.section.run_sets[0].pinned_run_ids[0]

    assert gid_a != gid_b
    assert base64.b64decode(gid_a).decode() == "Run:v1:g0dpjzew:project-a:entity-a"
    assert base64.b64decode(gid_b).decode() == "Run:v1:g0dpjzew:project-b:entity-b"


def test_from_model_decodes_legacy_gid_inputs():
    """`_from_model` decodes GID-encoded pinned/baseline values into slugs,
    so users always see the slug form on read regardless of what the spec
    happens to hold today."""
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(
            baseline_run="1mbku38n",
            pinned_runs=["1mbku38n", "2u1g3j1c"],
        ),
    )
    model = workspace._to_model()

    # Round-trip through the encoded GID form back to slugs
    decoded = ws.Workspace._from_model(model)
    assert decoded.runset_settings.baseline_run == "1mbku38n"
    assert decoded.runset_settings.pinned_runs == ["1mbku38n", "2u1g3j1c"]


def test_encode_passthrough_for_already_encoded_gid():
    """If the user happens to pass an already-encoded `Run:v1:` GID (e.g.
    from legacy code that did the base64 encoding by hand), the encoder
    leaves it alone instead of double-encoding it."""
    legacy_gid = base64.b64encode(
        b"Run:v1:g0dpjzew:legacy-project:legacy-entity"
    ).decode()
    workspace = ws.Workspace(
        entity="new-entity",
        project="new-project",
        runset_settings=ws.RunsetSettings(pinned_runs=[legacy_gid]),
    )

    pinned = workspace._to_model().spec.section.run_sets[0].pinned_run_ids
    assert pinned == [legacy_gid]


def test_baseline_run_auto_added_to_pinned():
    """Setting only baseline_run auto-adds it to pinned_runs (mirrors the W&B
    app's setRunPinnedAndBaseline write path)."""
    runset_settings = ws.RunsetSettings(baseline_run="1mbku38n")
    assert runset_settings.pinned_runs == ["1mbku38n"]


def test_baseline_already_in_pinned_not_duplicated():
    """If the user already includes the baseline in pinned_runs, the validator
    leaves the list untouched."""
    runset_settings = ws.RunsetSettings(
        baseline_run="1mbku38n",
        pinned_runs=["1mbku38n", "2u1g3j1c"],
    )
    assert runset_settings.pinned_runs == ["1mbku38n", "2u1g3j1c"]


def test_empty_baseline_and_pinned():
    """Defaults serialize cleanly: no baselineRunId / pinnedRunIds keys in the
    dumped spec, and round-trip yields the same defaults."""
    workspace = ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(),
    )

    model = workspace._to_model()
    runset = model.spec.section.run_sets[0]
    assert runset.baseline_run_id is None
    assert runset.pinned_run_ids is None

    dumped = model.spec.model_dump(by_alias=True, exclude_none=True)
    rs_dump = dumped["section"]["runSets"][0]
    assert "baselineRunId" not in rs_dump
    assert "pinnedRunIds" not in rs_dump

    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.baseline_run is None
    assert workspace2.runset_settings.pinned_runs == []


def test_pinned_runs_over_cap_warns():
    """Exceeding the app's MAX_PINNED_RUNS (20) emits a termwarn but still
    serializes every entry the user provided."""
    too_many = [f"run{i}" for i in range(21)]
    with patch("wandb_workspaces.workspaces.interface.wandb.termwarn") as warn:
        runset_settings = ws.RunsetSettings(pinned_runs=too_many)

    warn.assert_called_once()
    assert "21" in warn.call_args.args[0]
    assert runset_settings.pinned_runs == too_many
