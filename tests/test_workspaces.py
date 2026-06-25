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
import wandb_workspaces.workspaces.interface as ws_interface
from wandb_workspaces.workspaces._run_color_groups import (
    RUN_COLOR_GROUP_KEY_PREFIX,
    parse_run_color_group_key,
)
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


def test_workspace_url_uses_service_api_app_url_without_client():
    class _ServiceApi:
        app_url = "https://service.wandb.test/"

    class _Api:
        def __init__(self):
            self._service_api = _ServiceApi()

    with patch("wandb.Api", return_value=_Api()):
        workspace = ws.Workspace(entity="ent", project="proj")
        workspace._internal_name = "nw-abc123-v"

        assert workspace.url == "https://service.wandb.test/ent/proj?nw=abc123"


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


def _workspace_with_group_colors(groupby=None, group_colors=None):
    return ws.Workspace(
        entity="test-entity",
        project="test-project",
        runset_settings=ws.RunsetSettings(
            groupby=groupby or [],
            group_colors=group_colors or {},
        ),
    )


def _only_group_color(workspace):
    model = workspace._to_model()
    custom_run_color = model.spec.section.custom_run_colors
    assert len(custom_run_color) == 1
    key, color = next(iter(custom_run_color.items()))
    return model, parse_run_color_group_key(key), color


def _custom_run_colors(workspace):
    return workspace._to_model().spec.section.custom_run_colors


def _capture_termwarns(monkeypatch):
    warnings = []
    monkeypatch.setattr(ws_interface.wandb, "termwarn", warnings.append)
    return warnings


@pytest.mark.parametrize(
    ("groupby", "group_colors", "color", "path"),
    [
        (
            [ws.Metric("group")],
            {"sweep_alpha": "#4E79A7"},
            "#4E79A7",
            [{"kind": "group", "key": "run:group", "value": "sweep_alpha"}],
        ),
        (
            [ws.Metric("group"), ws.Config("model")],
            {ws.GroupPath("sweep_alpha", "model_vit"): "#59A14F"},
            "#59A14F",
            [
                {"kind": "group", "key": "run:group", "value": "sweep_alpha"},
                {"kind": "group", "key": "config:model.value", "value": "model_vit"},
            ],
        ),
    ],
)
def test_group_colors_serialize_path(groupby, group_colors, color, path):
    model, parsed, actual_color = _only_group_color(
        _workspace_with_group_colors(groupby=groupby, group_colors=group_colors)
    )

    assert model.spec.section.run_sets[0].id
    assert actual_color == color
    assert parsed == {
        "runset_id": model.spec.section.run_sets[0].id,
        "path": path,
    }


def test_invalid_group_colors_warn_and_omit(monkeypatch):
    workspace = _workspace_with_group_colors(
        groupby=[ws.Metric("group")],
        group_colors={
            ws.GroupPath(): "#111111",
            ws.GroupPath("sweep_alpha", "model_vit"): "#222222",
            ws.GroupPath("sweep_alpha", 1): "#333333",
            ws.GroupPath("sweep_beta"): 123,
        },
    )
    warnings = _capture_termwarns(monkeypatch)

    assert _custom_run_colors(workspace) == {}
    assert len(warnings) == 4
    assert any("empty GroupPath" in warning for warning in warnings)
    assert any("exceeds groupby depth" in warning for warning in warnings)
    assert any("segments must be strings" in warning for warning in warnings)
    assert any("color must be a string" in warning for warning in warnings)


def test_group_colors_without_groupby_warn_and_omit(monkeypatch):
    workspace = _workspace_with_group_colors(
        group_colors={"sweep_alpha": "#4E79A7"}
    )
    warnings = _capture_termwarns(monkeypatch)

    assert _custom_run_colors(workspace) == {}
    assert warnings == [
        "Omitting group_colors because runset_settings.groupby is empty."
    ]


def test_duplicate_group_color_path_warns_and_keeps_first(monkeypatch):
    workspace = _workspace_with_group_colors(
        groupby=[ws.Metric("group")],
        group_colors={
            "sweep_alpha": "#111111",
            ws.GroupPath("sweep_alpha"): "#222222",
        },
    )
    warnings = _capture_termwarns(monkeypatch)

    assert list(_custom_run_colors(workspace).values()) == ["#111111"]
    assert len(warnings) == 1
    assert "duplicate group color" in warnings[0]


def test_group_colors_round_trip_from_model():
    workspace = _workspace_with_group_colors(
        groupby=[
            ws.Metric("group"),
            ws.Config("model"),
            ws.Config("pbt.workspace.value"),
        ],
        group_colors={
            "sweep_alpha": "#4E79A7",
            ws.GroupPath("sweep_alpha", "model_vit"): "#59A14F",
        },
    )
    model = workspace._to_model()

    workspace2 = ws.Workspace._from_model(model)
    model2 = workspace2._to_model()

    assert [type(group) for group in workspace2.runset_settings.groupby] == [
        ws.Metric,
        ws.Config,
        ws.Config,
    ]
    assert [group.name for group in workspace2.runset_settings.groupby] == [
        "Group",
        "model",
        "pbt.workspace.value",
    ]
    assert [group.name for group in model2.spec.section.run_sets[0].grouping] == [
        "group",
        "model.value",
        "pbt.workspace.value",
    ]
    assert workspace2.runset_settings.group_colors == {
        "sweep_alpha": "#4E79A7",
        ws.GroupPath("sweep_alpha", "model_vit"): "#59A14F",
    }
    assert model2.spec.section.custom_run_colors == model.spec.section.custom_run_colors


def test_unknown_run_color_group_keys_round_trip_as_passthrough():
    workspace = _workspace_with_group_colors(groupby=[ws.Metric("group")])
    model = workspace._to_model()
    unknown_key = f"{RUN_COLOR_GROUP_KEY_PREFIX}not-json:also-not-json"
    model.spec.section.custom_run_colors[unknown_key] = "#123456"

    workspace2 = ws.Workspace._from_model(model)
    model2 = workspace2._to_model()

    assert workspace2.runset_settings.group_colors == {}
    assert (
        workspace2.runset_settings._custom_run_colors_passthrough[unknown_key]
        == "#123456"
    )
    assert model2.spec.section.custom_run_colors[unknown_key] == "#123456"


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


# Cross-project Pinned / Baseline Runs Tests


def test_cross_project_pinned_run_slash_form_roundtrip():
    """A cross-project pin given as 'entity/project/slug' encodes against the
    foreign (entity, project) and decodes back to a RunRef on read."""
    workspace = ws.Workspace(
        entity="my-entity",
        project="my-project",
        runset_settings=ws.RunsetSettings(
            pinned_runs=["other-team/other-project/abc1234"],
        ),
    )

    model = workspace._to_model()
    gid = model.spec.section.run_sets[0].pinned_run_ids[0]
    assert (
        base64.b64decode(gid).decode()
        == "Run:v1:abc1234:other-project:other-team"
    )

    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_runs == [
        ws.RunRef(slug="abc1234", entity="other-team", project="other-project"),
    ]


def test_cross_project_pinned_run_runref_roundtrip():
    """A cross-project pin given as a RunRef encodes against its explicit
    (entity, project) and decodes back to an equal RunRef."""
    pin = ws.RunRef("abc1234", entity="other-team", project="other-project")
    workspace = ws.Workspace(
        entity="my-entity",
        project="my-project",
        runset_settings=ws.RunsetSettings(pinned_runs=[pin]),
    )

    model = workspace._to_model()
    gid = model.spec.section.run_sets[0].pinned_run_ids[0]
    assert (
        base64.b64decode(gid).decode()
        == "Run:v1:abc1234:other-project:other-team"
    )

    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_runs == [pin]


def test_pinned_runs_mixed_same_and_cross_project():
    """A mixed list of bare-slug, slash-form, and RunRef entries each encode
    against the right (entity, project); decoded list keeps bare slugs as
    str and cross-project entries as RunRef."""
    workspace = ws.Workspace(
        entity="my-entity",
        project="my-project",
        runset_settings=ws.RunsetSettings(
            pinned_runs=[
                "same-proj-slug",
                "other-team/other-project/slash-slug",
                ws.RunRef("ref-slug", entity="t", project="p"),
            ],
        ),
    )

    model = workspace._to_model()
    gids = model.spec.section.run_sets[0].pinned_run_ids
    decoded = [base64.b64decode(g).decode() for g in gids]
    assert decoded == [
        "Run:v1:same-proj-slug:my-project:my-entity",
        "Run:v1:slash-slug:other-project:other-team",
        "Run:v1:ref-slug:p:t",
    ]

    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_runs == [
        "same-proj-slug",
        ws.RunRef(slug="slash-slug", entity="other-team", project="other-project"),
        ws.RunRef(slug="ref-slug", entity="t", project="p"),
    ]


def test_runref_defaults_to_workspace_entity_project():
    """A RunRef with `entity=None, project=None` is treated as same-project:
    encodes against the workspace's own (entity, project) and decodes back
    to a bare slug string (not a RunRef)."""
    workspace = ws.Workspace(
        entity="my-entity",
        project="my-project",
        runset_settings=ws.RunsetSettings(pinned_runs=[ws.RunRef("abc1234")]),
    )

    model = workspace._to_model()
    gid = model.spec.section.run_sets[0].pinned_run_ids[0]
    assert (
        base64.b64decode(gid).decode() == "Run:v1:abc1234:my-project:my-entity"
    )

    workspace2 = ws.Workspace._from_model(model)
    assert workspace2.runset_settings.pinned_runs == ["abc1234"]


def test_baseline_run_cross_project_auto_added_to_pinned():
    """A cross-project baseline (slash-form or RunRef) is auto-added to
    pinned_runs and survives the round-trip with its cross-project (entity,
    project) intact."""
    rs_slash = ws.RunsetSettings(
        baseline_run="other-team/other-project/abc1234",
    )
    assert rs_slash.pinned_runs == ["other-team/other-project/abc1234"]

    rs_ref = ws.RunsetSettings(
        baseline_run=ws.RunRef("abc1234", entity="other-team", project="other-project"),
    )
    assert rs_ref.pinned_runs == [
        ws.RunRef("abc1234", entity="other-team", project="other-project"),
    ]

    workspace = ws.Workspace(
        entity="my-entity",
        project="my-project",
        runset_settings=rs_slash,
    )
    model = workspace._to_model()
    runset = model.spec.section.run_sets[0]
    expected_gid = base64.b64encode(
        b"Run:v1:abc1234:other-project:other-team"
    ).decode()
    assert runset.baseline_run_id == expected_gid
    assert runset.pinned_run_ids == [expected_gid]

    workspace2 = ws.Workspace._from_model(model)
    expected_ref = ws.RunRef(
        slug="abc1234", entity="other-team", project="other-project"
    )
    assert workspace2.runset_settings.baseline_run == expected_ref
    assert workspace2.runset_settings.pinned_runs == [expected_ref]


def test_baseline_dedupe_across_input_forms():
    """Baseline given as RunRef and pinned given as slash-form for the same
    logical run is recognized as already pinned (no duplicate appended)."""
    runset_settings = ws.RunsetSettings(
        baseline_run=ws.RunRef("abc", entity="e", project="p"),
        pinned_runs=["e/p/abc"],
    )
    assert runset_settings.pinned_runs == ["e/p/abc"]


def test_invalid_slash_form_raises():
    """Slash-form strings with the wrong number of parts or with empty parts
    raise ValueError at serialization time with a clear message."""
    too_few = ws.Workspace(
        entity="e",
        project="p",
        runset_settings=ws.RunsetSettings(pinned_runs=["a/b"]),
    )
    with pytest.raises(ValueError, match="entity/project/slug"):
        too_few._to_model()

    too_many = ws.Workspace(
        entity="e",
        project="p",
        runset_settings=ws.RunsetSettings(pinned_runs=["a/b/c/d"]),
    )
    with pytest.raises(ValueError, match="entity/project/slug"):
        too_many._to_model()

    empty_part = ws.Workspace(
        entity="e",
        project="p",
        runset_settings=ws.RunsetSettings(pinned_runs=["a//c"]),
    )
    with pytest.raises(ValueError, match="non-empty"):
        empty_part._to_model()


def test_decoded_same_project_pin_is_bare_slug():
    """Regression guard: a same-project pin must round-trip back as a bare
    slug string, not as a slash-form string or a RunRef. This is what keeps
    pre-cross-project user code (and the existing test suite) working."""
    workspace = ws.Workspace(
        entity="my-entity",
        project="my-project",
        runset_settings=ws.RunsetSettings(
            baseline_run="abc1234",
            pinned_runs=["abc1234", "def5678"],
        ),
    )
    model = workspace._to_model()
    workspace2 = ws.Workspace._from_model(model)

    assert workspace2.runset_settings.baseline_run == "abc1234"
    assert workspace2.runset_settings.pinned_runs == ["abc1234", "def5678"]
    for entry in workspace2.runset_settings.pinned_runs:
        assert isinstance(entry, str)
        assert "/" not in entry
    assert isinstance(workspace2.runset_settings.baseline_run, str)
