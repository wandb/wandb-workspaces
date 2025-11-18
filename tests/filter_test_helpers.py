"""Shared test helpers for filter functionality across workspaces and reports.

This module contains common test logic that is used by both workspace and report
filter tests to ensure consistency and reduce duplication.
"""

import warnings
from typing import Any, Callable, List, Protocol, Union

import pytest

import wandb_workspaces.expr as expr


class FilterContainer(Protocol):
    """Protocol for objects that contain filters (RunsetSettings or Runset)."""

    filters: Union[str, List[Any]]


def create_runset_settings(filters) -> FilterContainer:
    """Factory function for creating workspace RunsetSettings."""
    import wandb_workspaces.workspaces as ws

    return ws.RunsetSettings(filters=filters)


def create_runset(filters) -> FilterContainer:
    """Factory function for creating reports Runset."""
    import wandb_workspaces.reports.v2 as wr

    return wr.Runset(entity="test", project="test", filters=filters)


def verify_string_filter_acceptance(container_factory: Callable):
    """Verify that string filters are accepted and properly converted."""
    # Test with string filter
    container1 = container_factory(filters='Config("lr") == 0.01')
    assert isinstance(container1.filters, str)
    assert "lr" in container1.filters

    # Test with FilterExpr list (should convert to string)
    filter_list = [expr.Config("lr") == 0.01]
    container2 = container_factory(filters=filter_list)
    assert isinstance(container2.filters, str)
    assert "lr" in container2.filters


def verify_filterexpr_list_acceptance(container_factory: Callable):
    """Verify that FilterExpr lists are properly converted to string expressions."""
    filter_list = [expr.Config("lr") == 0.01, expr.Metric("loss") <= 1.0]
    container = container_factory(filters=filter_list)

    # Filters should be converted to string
    assert isinstance(container.filters, str)
    assert "lr" in container.filters
    assert "loss" in container.filters


def verify_operator_mapping_string_filters(container_factory: Callable):
    """Verify that < and > operators in string filters are mapped to <= and >=."""
    from wandb_workspaces.expr import expr_to_filters

    # Test < operator (should map to <= with warning during parsing)
    container1 = container_factory(filters='Metric("loss") < 1.0')
    with pytest.warns(UserWarning, match="'<' operator.*mapped to '<='"):
        parsed1 = expr_to_filters(container1.filters)
    assert parsed1.filters[0].filters[0].op == "<="

    # Test > operator (should map to >= with warning during parsing)
    container2 = container_factory(filters='Metric("accuracy") > 0.9')
    with pytest.warns(UserWarning, match="'>' operator.*mapped to '>='"):
        parsed2 = expr_to_filters(container2.filters)
    assert parsed2.filters[0].filters[0].op == ">="

    # Test <= and >= operators (should NOT trigger warnings)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        container3 = container_factory(filters='Metric("loss") <= 1.0')
        parsed3 = expr_to_filters(container3.filters)
        # Filter for warnings that contain both "operator" and "mapped to"
        relevant_warnings = [
            warning
            for warning in w
            if "operator" in str(warning.message).lower()
            and "mapped to" in str(warning.message).lower()
        ]
        assert len(relevant_warnings) == 0
        assert parsed3.filters[0].filters[0].op == "<="


def verify_operator_mapping_filterexpr(container_factory: Callable):
    """Verify that < and > operators in FilterExpr objects are mapped to <= and >=."""
    # Test < operator with FilterExpr
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        filter_list = [expr.Metric("loss") < 1.0]
        container1 = container_factory(filters=filter_list)
        relevant_warnings = [
            warning
            for warning in w
            if "operator" in str(warning.message).lower()
            and "mapped to" in str(warning.message).lower()
        ]
        assert len(relevant_warnings) == 1
        assert container1.filters is not None

    # Test > operator with FilterExpr
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        filter_list = [expr.Metric("accuracy") > 0.9]
        container2 = container_factory(filters=filter_list)
        relevant_warnings = [
            warning
            for warning in w
            if "operator" in str(warning.message).lower()
            and "mapped to" in str(warning.message).lower()
        ]
        assert len(relevant_warnings) == 1
        assert container2.filters is not None

    # Test <= and >= operators (should NOT trigger warnings)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        filter_list = [expr.Metric("loss") <= 1.0, expr.Metric("accuracy") >= 0.9]
        container3 = container_factory(filters=filter_list)
        relevant_warnings = [
            warning
            for warning in w
            if "operator" in str(warning.message).lower()
            and "mapped to" in str(warning.message).lower()
        ]
        assert len(relevant_warnings) == 0
        assert container3.filters is not None


def verify_summary_alias_support(container_factory: Callable):
    """Verify that both Summary and SummaryMetric can be used in string filters."""
    # Test with SummaryMetric
    container1 = container_factory(filters='SummaryMetric("accuracy") >= 0.9')
    assert isinstance(container1.filters, str)
    assert "accuracy" in container1.filters

    # Test with Summary (alias)
    container2 = container_factory(filters='Summary("accuracy") >= 0.9')
    assert isinstance(container2.filters, str)
    assert "accuracy" in container2.filters

    # Test with FilterExpr using Summary
    filter_list = [expr.Summary("accuracy") >= 0.9]
    container3 = container_factory(filters=filter_list)
    assert isinstance(container3.filters, str)
    assert "accuracy" in container3.filters


# Core filter expression tests (not container-specific)


def test_expression_parsing():
    """Test the core expr_to_filters parsing function with various expressions."""
    from wandb_workspaces.expr import expr_to_filters, Filters, Key

    test_cases = [
        ("", []),
        (
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
        ),
        (
            "b == 1 and c == 2",
            [
                Filters(
                    op="=",
                    key=Key(section="run", name="b"),
                    filters=None,
                    value=1,
                    disabled=False,
                ),
                Filters(
                    op="=",
                    key=Key(section="run", name="c"),
                    filters=None,
                    value=2,
                    disabled=False,
                ),
            ],
        ),
        (
            "b = 1 and c = 2",
            [
                Filters(
                    op="=",
                    key=Key(section="run", name="b"),
                    filters=None,
                    value=1,
                    disabled=False,
                ),
                Filters(
                    op="=",
                    key=Key(section="run", name="c"),
                    filters=None,
                    value=2,
                    disabled=False,
                ),
            ],
        ),
        (
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
        ),
        (
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
        ),
        (
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
        ),
        (
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
        ),
        (
            "Config('param') = 'value'",
            [
                Filters(
                    op="=",
                    key=Key(section="config", name="param"),
                    filters=None,
                    value="value",
                    disabled=False,
                )
            ],
        ),
        (
            "SummaryMetric('accuracy') = 0.95",
            [
                Filters(
                    op="=",
                    key=Key(section="summary", name="accuracy"),
                    filters=None,
                    value=0.95,
                    disabled=False,
                )
            ],
        ),
    ]

    for expr_str, expected_filters in test_cases:
        result = expr_to_filters(expr_str)
        expected = Filters(
            op="OR", filters=[Filters(op="AND", filters=expected_filters)]
        )
        assert result == expected, f"Failed for expression: {expr_str}"


def test_filter_expr_to_model():
    """Test FilterExpr.to_model() for various filter expressions."""
    test_cases = [
        (
            expr.Metric("abc") > 1,
            {
                "op": ">=",  # > maps to >= internally
                "key": {"section": "run", "name": "abc"},
                "value": 1,
                "disabled": False,
            },
        ),
        (
            expr.Metric("Name") != "tomato",
            {
                "op": "!=",
                "key": {"section": "run", "name": "displayName"},
                "value": "tomato",
                "disabled": False,
            },
        ),
        (
            expr.Metric("Tags").isin(["ppo", "4pool"]),
            {
                "op": "IN",
                "key": {"section": "run", "name": "tags"},
                "value": ["ppo", "4pool"],
                "disabled": False,
            },
        ),
    ]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Ignore operator mapping warnings
        for filter_expr, expected_spec in test_cases:
            result = filter_expr.to_model().model_dump(by_alias=True, exclude_none=True)
            assert result == expected_spec, f"Failed for expression: {filter_expr}"


def verify_within_last_filterexpr(container_factory: Callable):
    """Verify that within_last method works with FilterExpr objects."""
    # Test within_last with different time units (all using CreatedTimestamp)
    filter_list_days = [expr.Metric("CreatedTimestamp").within_last(5, "days")]
    container1 = container_factory(filters=filter_list_days)
    assert isinstance(container1.filters, str)
    assert "within_last" in container1.filters
    assert "CreatedTimestamp" in container1.filters
    assert "5" in container1.filters
    assert "days" in container1.filters

    # Test with hours
    filter_list_hours = [expr.Metric("CreatedTimestamp").within_last(2, "hours")]
    container2 = container_factory(filters=filter_list_hours)
    assert isinstance(container2.filters, str)
    assert "within_last" in container2.filters
    assert "CreatedTimestamp" in container2.filters
    assert "2" in container2.filters
    assert "hours" in container2.filters

    # Test with minutes
    filter_list_minutes = [expr.Metric("CreatedTimestamp").within_last(30, "minutes")]
    container3 = container_factory(filters=filter_list_minutes)
    assert isinstance(container3.filters, str)
    assert "within_last" in container3.filters
    assert "30" in container3.filters
    assert "minutes" in container3.filters


def verify_within_last_string_filters(container_factory: Callable):
    """Verify that WithinLast works in string filter expressions."""
    from wandb_workspaces.expr import expr_to_filters

    # Test WithinLast with days
    container1 = container_factory(
        filters="WithinLast(Metric('CreatedTimestamp'), 5, 'days')"
    )
    parsed1 = expr_to_filters(container1.filters)
    assert parsed1.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed1.filters[0].filters[0].value == 432000  # 5 days in seconds

    # Test WithinLast with hours
    container2 = container_factory(
        filters="WithinLast(Metric('CreatedTimestamp'), 2, 'hours')"
    )
    parsed2 = expr_to_filters(container2.filters)
    assert parsed2.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed2.filters[0].filters[0].value == 7200  # 2 hours in seconds

    # Test WithinLast with minutes
    container3 = container_factory(
        filters="WithinLast(Metric('CreatedTimestamp'), 30, 'minutes')"
    )
    parsed3 = expr_to_filters(container3.filters)
    assert parsed3.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed3.filters[0].filters[0].value == 1800  # 30 minutes in seconds


def verify_within_last_operator_syntax(container_factory: Callable):
    """Verify that within_last operator syntax works in string filters."""
    from wandb_workspaces.expr import expr_to_filters

    # Test within_last operator with days
    container1 = container_factory(
        filters="Metric('CreatedTimestamp') within_last 5 days"
    )
    parsed1 = expr_to_filters(container1.filters)
    assert parsed1.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed1.filters[0].filters[0].value == 432000  # 5 days in seconds

    # Test with hours
    container2 = container_factory(
        filters="Metric('CreatedTimestamp') within_last 2 hours"
    )
    parsed2 = expr_to_filters(container2.filters)
    assert parsed2.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed2.filters[0].filters[0].value == 7200  # 2 hours in seconds

    # Test with minutes
    container3 = container_factory(
        filters="Metric('CreatedTimestamp') within_last 30 minutes"
    )
    parsed3 = expr_to_filters(container3.filters)
    assert parsed3.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed3.filters[0].filters[0].value == 1800  # 30 minutes in seconds

    # Test combined with other filters
    container4 = container_factory(
        filters="Metric('CreatedTimestamp') within_last 7 days and State == 'finished'"
    )
    parsed4 = expr_to_filters(container4.filters)
    assert len(parsed4.filters[0].filters) == 2
    assert parsed4.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed4.filters[0].filters[1].op == "="

    # Test with singular unit names
    container5 = container_factory(
        filters="Metric('CreatedTimestamp') within_last 1 day"
    )
    parsed5 = expr_to_filters(container5.filters)
    assert parsed5.filters[0].filters[0].op == "WITHINSECONDS"
    assert parsed5.filters[0].filters[0].value == 86400  # 1 day in seconds


def test_within_last_time_conversion():
    """Test the time conversion utilities."""
    from wandb_workspaces.expr import _convert_time_to_seconds, _convert_seconds_to_time

    # Test conversion to seconds
    assert _convert_time_to_seconds(5, "days") == 432000
    assert _convert_time_to_seconds(2, "hours") == 7200
    assert _convert_time_to_seconds(30, "minutes") == 1800
    assert _convert_time_to_seconds(1, "day") == 86400
    assert _convert_time_to_seconds(1, "hour") == 3600
    assert _convert_time_to_seconds(1, "minute") == 60

    # Test conversion from seconds (clean divisions)
    assert _convert_seconds_to_time(432000) == (5, "days")
    assert _convert_seconds_to_time(86400) == (1, "days")
    assert _convert_seconds_to_time(7200) == (2, "hours")
    assert _convert_seconds_to_time(3600) == (1, "hours")
    assert _convert_seconds_to_time(1800) == (30, "minutes")
    assert _convert_seconds_to_time(60) == (1, "minutes")

    # Test conversion from seconds (non-clean divisions)
    # Should prefer appropriate units
    amount, unit = _convert_seconds_to_time(90)  # 1.5 minutes
    assert unit == "minutes"
    assert amount == 1.5

    amount, unit = _convert_seconds_to_time(5400)  # 90 minutes (divisible by 60)
    assert unit == "minutes"
    assert amount == 90

    # Test a value that truly needs decimal hours
    amount, unit = _convert_seconds_to_time(5500)  # Not divisible by 60 or 3600
    assert unit == "hours"
    assert abs(amount - 1.527777) < 0.0001  # ~1.528 hours


def test_within_last_round_trip():
    """Test that FilterExpr → string → FilterExpr preserves semantics."""
    from wandb_workspaces.expr import (
        expr_to_filters,
        filters_to_expr,
        filter_expr_to_filters_tree,
        filters_tree_to_filter_expr,
    )

    # Test round-trip with FilterExpr
    original_filters = [expr.Metric("CreatedTimestamp").within_last(5, "days")]
    filters_tree = filter_expr_to_filters_tree(original_filters)
    string_expr = filters_to_expr(filters_tree)

    # Verify it outputs operator syntax
    assert "within_last" in string_expr
    assert "5 days" in string_expr

    # Parse the string back
    parsed_tree = expr_to_filters(string_expr)
    result_filters = filters_tree_to_filter_expr(parsed_tree)

    # Check that the semantics are preserved
    assert len(result_filters) == 1
    assert result_filters[0].op == "WITHINSECONDS"
    assert result_filters[0].key.name == "CreatedTimestamp"
    assert result_filters[0].value == 432000  # 5 days in seconds


def test_within_last_validation():
    """Test that within_last only works with CreatedTimestamp."""
    import pytest

    # Should work with CreatedTimestamp
    filter1 = expr.Metric("CreatedTimestamp").within_last(5, "days")
    assert filter1.op == "WITHINSECONDS"

    # Should fail with other fields
    with pytest.raises(ValueError, match="only available for CreatedTimestamp"):
        expr.Metric("State").within_last(5, "days")

    with pytest.raises(ValueError, match="only available for CreatedTimestamp"):
        expr.Metric("WallTime").within_last(2, "hours")

    with pytest.raises(ValueError, match="only available for CreatedTimestamp"):
        expr.Config("learning_rate").within_last(1, "day")

    with pytest.raises(ValueError, match="only available for CreatedTimestamp"):
        expr.Summary("accuracy").within_last(7, "days")

    # Test string filter validation
    from wandb_workspaces.expr import expr_to_filters

    # Should work
    valid = expr_to_filters("Metric('CreatedTimestamp') within_last 5 days")
    assert valid.filters[0].filters[0].op == "WITHINSECONDS"

    # Should fail
    with pytest.raises(ValueError, match="only available for CreatedTimestamp"):
        expr_to_filters("Metric('State') within_last 5 days")

    with pytest.raises(ValueError, match="only available for CreatedTimestamp"):
        expr_to_filters("WithinLast(Metric('WallTime'), 2, 'hours')")
