"""Unified filter tests for both workspaces and reports.

This test module uses pytest parameterization to run the same test logic
against both workspace RunsetSettings and report Runset objects, ensuring
consistent filter behavior across the codebase.

It also includes core filter expression tests that are not container-specific.
"""

import pytest

from .filter_test_helpers import (
    create_runset,
    create_runset_settings,
    test_expression_parsing,
    test_filter_expr_to_model,
    test_within_last_round_trip,
    test_within_last_time_conversion,
    verify_filterexpr_list_acceptance,
    verify_operator_mapping_filterexpr,
    verify_operator_mapping_string_filters,
    verify_string_filter_acceptance,
    verify_summary_alias_support,
    verify_within_last_filterexpr,
    verify_within_last_operator_syntax,
    verify_within_last_string_filters,
)

# Parameterize tests to run against both workspace and report filter containers
FILTER_CONTAINERS = [
    pytest.param(create_runset_settings, id="workspace_RunsetSettings"),
    pytest.param(create_runset, id="reports_Runset"),
]


# ===== Container-agnostic tests (workspaces and reports) =====


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_string_filter_acceptance(container_factory):
    """Test that both workspaces and reports accept string filters."""
    verify_string_filter_acceptance(container_factory)


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_filterexpr_list_acceptance(container_factory):
    """Test that both workspaces and reports accept FilterExpr lists."""
    verify_filterexpr_list_acceptance(container_factory)


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_operator_mapping_string_filters(container_factory):
    """Test that < and > operators are mapped to <= and >= in string filters."""
    verify_operator_mapping_string_filters(container_factory)


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_operator_mapping_filterexpr(container_factory):
    """Test that < and > operators are mapped to <= and >= in FilterExpr objects."""
    verify_operator_mapping_filterexpr(container_factory)


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_summary_alias_support(container_factory):
    """Test that both Summary and SummaryMetric aliases work in filters."""
    verify_summary_alias_support(container_factory)


# ===== Core filter expression tests (not container-specific) =====


def test_core_expression_parsing():
    """Test the core expr_to_filters parsing function."""
    test_expression_parsing()


def test_core_filter_expr_to_model():
    """Test FilterExpr.to_model() for various filter expressions."""
    test_filter_expr_to_model()


# ===== Within Last filter tests =====


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_within_last_filterexpr(container_factory):
    """Test that within_last method works with FilterExpr objects in both workspaces and reports."""
    verify_within_last_filterexpr(container_factory)


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_within_last_string_filters(container_factory):
    """Test that WithinLast works in string filter expressions in both workspaces and reports."""
    verify_within_last_string_filters(container_factory)


@pytest.mark.parametrize("container_factory", FILTER_CONTAINERS)
def test_unified_within_last_operator_syntax(container_factory):
    """Test that within_last operator syntax works in string filters in both workspaces and reports."""
    verify_within_last_operator_syntax(container_factory)


def test_core_within_last_time_conversion():
    """Test the time conversion utilities for within_last."""
    test_within_last_time_conversion()


def test_core_within_last_round_trip():
    """Test that FilterExpr → string → FilterExpr preserves semantics for within_last."""
    test_within_last_round_trip()


def test_core_within_last_validation():
    """Test that within_last validation works correctly."""
    from .filter_test_helpers import test_within_last_validation

    test_within_last_validation()


# ===== Binary and unary operation tests =====


def test_binary_operations_in_filters():
    """Test that binary operations in filter values are supported (e.g., 0.5 + 0.45)."""
    from wandb_workspaces import expr

    test_cases = [
        "Summary('accuracy') > 0.5 + 0.45",  # Addition
        "Config('epochs') == 100 - 10",  # Subtraction
        "Summary('loss') < 0.5 * 2",  # Multiplication
        "Config('batch_size') >= 64 / 2",  # Division
        "Summary('floor') >= 100 // 3",  # Floor division
        "Config('mod') == 10 % 3",  # Modulo
        "Summary('power') > 2 ** 3",  # Power
    ]

    for test_expr in test_cases:
        # Should not raise "Unsupported value type" error
        result = expr.expr_to_filters(test_expr)
        assert result is not None
        assert isinstance(result, expr.Filters)


def test_unary_operations_in_filters():
    """Test that unary operations in filter values are supported (e.g., -5, +3)."""
    from wandb_workspaces import expr

    test_cases = [
        "Summary('value') > -5",  # Unary minus
        "Config('threshold') == +10",  # Unary plus (though less common)
    ]

    for test_expr in test_cases:
        # Should not raise "Unsupported value type" error
        result = expr.expr_to_filters(test_expr)
        assert result is not None
        assert isinstance(result, expr.Filters)


def test_list_with_dashes_round_trip():
    """Test that list values with dashes in strings survive round-trip conversion.

    Regression test: strings with dashes like 'run-one' were not quoted when
    converting filters to expressions, causing them to be parsed as subtraction.
    """
    from wandb_workspaces import expr

    # Create a filter with list containing strings with dashes
    filters = expr.Filters(
        op="IN",
        key=expr.Key(section="run", name="Name"),
        value=["run-one", "two-three", "abc-123-def"],
    )

    # Convert to expression string
    expr_string = expr.filters_to_expr(filters)

    # The expression should properly quote the strings
    assert "'run-one'" in expr_string
    assert "'two-three'" in expr_string
    assert "'abc-123-def'" in expr_string

    # Parse it back - should not raise TypeError about string subtraction
    parsed = expr.expr_to_filters(expr_string)
    assert parsed is not None

    # Verify the values survived the round-trip (nested in OR/AND structure)
    inner_filter = parsed.filters[0].filters[0]
    assert inner_filter.value == ["run-one", "two-three", "abc-123-def"]


# ===== Disabled filter state preservation tests =====


def test_disabled_filters_preserved_in_runset_roundtrip():
    """Disabled (inactive) filters must survive a _from_model → _to_model roundtrip.

    Regression test: filters_to_expr discarded the ``disabled`` flag and
    expr_to_filters hardcoded ``disabled=False``, so inactive filters
    silently became active after a load/save cycle (e.g. report migration).
    """
    from wandb_workspaces import expr
    from wandb_workspaces.reports.v2 import internal
    import wandb_workspaces.reports.v2 as wr

    internal_runset = internal.Runset(
        name="test",
        filters=expr.Filters(
            op="OR",
            filters=[
                expr.Filters(
                    op="AND",
                    filters=[
                        expr.Filters(op="=", key=expr.Key(section="run", name="username"), value="alice", disabled=False),
                        expr.Filters(op="=", key=expr.Key(section="run", name="state"), value="running", disabled=True),
                        expr.Filters(op=">=", key=expr.Key(section="run", name="duration"), value="3600", disabled=True),
                    ],
                )
            ],
        ),
    )

    iface = wr.Runset._from_model(internal_runset)
    model = iface._to_model()
    leaves = model.filters.filters[0].filters

    assert leaves[0].disabled is False
    assert leaves[1].disabled is True
    assert leaves[2].disabled is True


def test_user_constructed_runset_parses_from_string():
    """Runsets built by the user (not loaded) should parse filters from the string."""
    import wandb_workspaces.reports.v2 as wr

    rs = wr.Runset(filters="Metric('User') == 'alice'")
    assert rs._filters_internal is None

    model = rs._to_model()
    leaves = model.filters.filters[0].filters
    assert leaves[0].value == "alice"
    assert leaves[0].disabled is False


def test_modifying_filters_after_load_uses_new_value():
    """Overwriting .filters on a loaded Runset must discard the stashed tree."""
    from wandb_workspaces import expr
    from wandb_workspaces.reports.v2 import internal
    import wandb_workspaces.reports.v2 as wr

    internal_runset = internal.Runset(
        name="test",
        filters=expr.Filters(
            op="OR",
            filters=[
                expr.Filters(
                    op="AND",
                    filters=[
                        expr.Filters(op="=", key=expr.Key(section="run", name="username"), value="alice", disabled=True),
                    ],
                )
            ],
        ),
    )

    iface = wr.Runset._from_model(internal_runset)
    assert iface._filters_internal is not None

    iface.filters = "Metric('User') == 'bob'"

    model = iface._to_model()
    leaves = model.filters.filters[0].filters
    assert leaves[0].value == "bob", "New filter value should take effect"
    assert leaves[0].disabled is False, "New filter should be active"


# ===== v2 filter read/conversion tests =====

class TestV2ToString:
    """Test conversion from v2 flat filter format to display string."""

    def test_simple_v2_and(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "disabled": False, "connector": "AND"},
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == 'Metric("State") == \'finished\' and Config("lr") == 0.01'

    def test_simple_v2_or(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "disabled": False, "connector": "OR"},
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == 'Metric("State") == \'finished\' or Config("lr") == 0.01'

    def test_v2_and_then_or(self):
        """Corresponds to: state=finished AND lr=0.01 OR lr=0.1"""
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "disabled": False, "connector": "AND"},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.1, "disabled": False, "connector": "OR"},
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == (
            'Metric("State") == \'finished\' and Config("lr") == 0.01 or Config("lr") == 0.1'
        )

    def test_v2_with_group(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {
                    "filters": [
                        {"op": "=", "key": {"section": "run", "name": "host"}, "value": "abc", "disabled": False},
                        {"op": "=", "key": {"section": "run", "name": "host"}, "value": "xyz", "disabled": False, "connector": "OR"},
                    ],
                    "disabled": False,
                    "connector": "AND",
                },
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == (
            'Metric("State") == \'finished\' and '
            '(Metric("Hostname") == \'abc\' or Metric("Hostname") == \'xyz\')'
        )

    def test_v2_disabled_items_skipped(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "run", "name": ""}, "value": "", "disabled": True, "connector": "AND"},
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == 'Metric("State") == \'finished\''

    def test_v2_empty_filters(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [],
        }
        result = filters_v2_to_string(v2)
        assert result == ""

    def test_is_filter_v2(self):
        from wandb_workspaces.expr import is_filter_v2

        assert is_filter_v2({"filterFormat": "filterV2", "filters": []})
        assert not is_filter_v2({"op": "OR", "filters": []})
        assert not is_filter_v2({"filterFormat": "other"})
        assert not is_filter_v2("not a dict")

    def test_v2_within_last(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"key": {"section": "run", "name": "createdAt"}, "op": "WITHINSECONDS", "value": 432000},
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == 'Metric("CreatedTimestamp") within_last 5 days'

    def test_v2_in_operator(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"key": {"section": "run", "name": "tags"}, "op": "IN", "value": ["prod", "staging"]},
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == 'Metric("Tags") in [\'prod\', \'staging\']'

    def test_v2_nin_operator(self):
        from wandb_workspaces.expr import filters_v2_to_string

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"key": {"section": "run", "name": "tags"}, "op": "NIN", "value": ["debug", "test"]},
            ],
        }
        result = filters_v2_to_string(v2)
        assert result == 'Metric("Tags") not in [\'debug\', \'test\']'


class TestV2DirectFilterRoundTrip:
    """Test that v2 filters are stored directly in Runset.filters and round-trip correctly."""

    def test_v2_filters_stored_as_dict(self):
        """v2 filter dict should be stored directly in runset.filters."""
        from copy import deepcopy

        from wandb_workspaces.workspaces.internal import WorkspaceViewspec

        original_v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished"},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "connector": "AND"},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.1, "connector": "OR"},
            ],
        }
        spec_dict = {
            "section": {
                "panelBankConfig": {"state": 0, "settings": {}, "sections": []},
                "panelBankSectionConfig": {"pinned": False},
                "customRunColors": {},
                "runSets": [{"id": "rs1", "filters": deepcopy(original_v2)}],
            }
        }

        parsed_spec = WorkspaceViewspec.model_validate(spec_dict)
        filters = parsed_spec.section.run_sets[0].filters
        assert isinstance(filters, dict)
        assert filters["filterFormat"] == "filterV2"
        assert len(filters["filters"]) == 3

        spec_out = parsed_spec.model_dump(by_alias=True, exclude_none=True)
        assert spec_out["section"]["runSets"][0]["filters"] == original_v2

    def test_legacy_filters_stored_as_model(self):
        """Legacy (non-v2) filters should be parsed into Filters model."""
        from wandb_workspaces.workspaces.internal import WorkspaceViewspec

        spec_dict = {
            "section": {
                "panelBankConfig": {"state": 0, "settings": {}, "sections": []},
                "panelBankSectionConfig": {"pinned": False},
                "customRunColors": {},
                "runSets": [{
                    "id": "rs1",
                    "filters": {
                        "op": "OR",
                        "filters": [{"op": "AND", "filters": [
                            {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "disabled": False}
                        ]}]
                    },
                }],
            }
        }

        parsed_spec = WorkspaceViewspec.model_validate(spec_dict)
        filters = parsed_spec.section.run_sets[0].filters
        assert not isinstance(filters, dict)
        assert filters.op == "OR"
