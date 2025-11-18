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
