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


# ===== OR filter and v2 deserialization tests =====


class TestOrStringFilters:
    """Test OR support via string filter expressions."""

    def test_simple_or(self):
        from wandb_workspaces import expr

        tree = expr.expr_to_filters(
            "Metric('State') == 'finished' or Config('lr') == 0.01"
        )
        assert tree.op == "OR"
        assert len(tree.filters) == 2
        assert tree.filters[0].op == "AND"
        assert tree.filters[1].op == "AND"
        assert tree.filters[0].filters[0].value == "finished"
        assert tree.filters[1].filters[0].value == 0.01

    def test_and_or_precedence(self):
        from wandb_workspaces import expr

        tree = expr.expr_to_filters(
            "Metric('State') == 'finished' and Config('lr') == 0.01 or Config('lr') == 0.1"
        )
        assert tree.op == "OR"
        assert len(tree.filters) == 2
        # First bucket: (State AND lr==0.01)
        assert tree.filters[0].op == "AND"
        assert len(tree.filters[0].filters) == 2
        # Second bucket: (lr==0.1)
        assert tree.filters[1].op == "AND"

    def test_or_round_trip(self):
        from wandb_workspaces import expr

        original = "Metric('State') == 'finished' or Config('lr') == 0.01"
        tree = expr.expr_to_filters(original)
        result = expr.filters_to_expr(tree)
        re_tree = expr.expr_to_filters(result)
        assert len(re_tree.filters) == 2

    def test_parenthesised_or_in_and(self):
        from wandb_workspaces import expr

        tree = expr.expr_to_filters(
            "(Config('lr') == 0.01 or Config('lr') == 0.1) and Metric('State') == 'finished'"
        )
        assert tree.op == "OR"


class TestOrObjectAPI:
    """Test OR support via the Or/And/Group object API."""

    def test_or_filterexpr(self):
        from wandb_workspaces import expr

        f = expr.Or(
            expr.Config("lr") == 0.01,
            expr.Config("lr") == 0.1,
        )
        tree = f.to_model()
        assert tree.op == "OR"
        assert len(tree.filters) == 2

    def test_and_filterexpr(self):
        from wandb_workspaces import expr

        f = expr.And(
            expr.Config("lr") == 0.01,
            expr.Metric("State") == "finished",
        )
        tree = f.to_model()
        assert tree.op == "AND"
        assert len(tree.filters) == 2

    def test_or_with_and_groups(self):
        from wandb_workspaces import expr

        f = expr.Or(
            expr.And(expr.Config("lr") == 0.01, expr.Metric("State") == "finished"),
            expr.Config("lr") == 0.1,
        )
        tree = f.to_model()
        assert tree.op == "OR"
        assert len(tree.filters) == 2
        assert tree.filters[0].op == "AND"
        assert len(tree.filters[0].filters) == 2
        assert tree.filters[1].op == "AND"
        assert len(tree.filters[1].filters) == 1

    def test_or_in_runset_settings(self):
        import wandb_workspaces.workspaces as ws
        from wandb_workspaces import expr

        rs = ws.RunsetSettings(
            filters=expr.Or(
                expr.Config("lr") == 0.01,
                expr.Config("lr") == 0.1,
            )
        )
        assert isinstance(rs.filters, str)
        assert "or" in rs.filters

    def test_or_list_in_runset_settings(self):
        import wandb_workspaces.workspaces as ws
        from wandb_workspaces import expr

        rs = ws.RunsetSettings(
            filters=[
                expr.Or(
                    expr.Config("lr") == 0.01,
                    expr.Config("lr") == 0.1,
                )
            ]
        )
        assert isinstance(rs.filters, str)
        assert "or" in rs.filters


class TestV2Deserialization:
    """Test conversion from v2 flat filter format to legacy tree."""

    def test_simple_v2_and(self):
        from wandb_workspaces.expr import filters_v2_to_filters_tree

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "disabled": False, "connector": "AND"},
            ],
        }
        tree = filters_v2_to_filters_tree(v2)
        assert tree.op == "OR"
        assert len(tree.filters) == 1
        and_bucket = tree.filters[0]
        assert and_bucket.op == "AND"
        assert len(and_bucket.filters) == 2
        assert and_bucket.filters[0].value == "finished"
        assert and_bucket.filters[1].value == 0.01

    def test_simple_v2_or(self):
        from wandb_workspaces.expr import filters_v2_to_filters_tree

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "disabled": False, "connector": "OR"},
            ],
        }
        tree = filters_v2_to_filters_tree(v2)
        assert tree.op == "OR"
        assert len(tree.filters) == 2

    def test_v2_and_then_or(self):
        """Corresponds to: state=finished AND lr=0.01 OR lr=0.1"""
        from wandb_workspaces.expr import filters_v2_to_filters_tree

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "disabled": False, "connector": "AND"},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.1, "disabled": False, "connector": "OR"},
            ],
        }
        tree = filters_v2_to_filters_tree(v2)
        assert tree.op == "OR"
        assert len(tree.filters) == 2
        assert tree.filters[0].op == "AND"
        assert len(tree.filters[0].filters) == 2
        assert tree.filters[1].op == "AND"
        assert tree.filters[1].filters[0].value == 0.1

    def test_v2_with_group(self):
        from wandb_workspaces.expr import filters_v2_to_filters_tree

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
        tree = filters_v2_to_filters_tree(v2)
        assert tree.op == "OR"
        and_bucket = tree.filters[0]
        assert and_bucket.op == "AND"
        assert len(and_bucket.filters) == 2
        assert and_bucket.filters[0].value == "finished"
        # The nested group produces an OR node
        nested = and_bucket.filters[1]
        assert nested.op == "OR"

    def test_v2_disabled_items_skipped(self):
        from wandb_workspaces.expr import filters_v2_to_filters_tree

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "run", "name": ""}, "value": "", "disabled": True, "connector": "AND"},
            ],
        }
        tree = filters_v2_to_filters_tree(v2)
        and_bucket = tree.filters[0]
        assert len(and_bucket.filters) == 1

    def test_v2_empty_filters(self):
        from wandb_workspaces.expr import filters_v2_to_filters_tree

        v2 = {
            "filterFormat": "filterV2",
            "filters": [],
        }
        tree = filters_v2_to_filters_tree(v2)
        assert tree.op == "OR"

    def test_is_filter_v2(self):
        from wandb_workspaces.expr import is_filter_v2

        assert is_filter_v2({"filterFormat": "filterV2", "filters": []})
        assert not is_filter_v2({"op": "OR", "filters": []})
        assert not is_filter_v2({"filterFormat": "other"})
        assert not is_filter_v2("not a dict")

    def test_real_world_v2_payload(self):
        """Test with the exact payload observed from the UI in the debugging session."""
        from wandb_workspaces.expr import filters_v2_to_filters_tree, filters_to_expr

        v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished", "disabled": False},
                {"op": "=", "key": {"section": "config", "name": "learning_rate.value"}, "value": 0.001, "disabled": False, "connector": "AND"},
                {
                    "filters": [
                        {"key": {"section": "run", "name": "host"}, "op": "=", "value": "CW-JHWYNJMYJF-L", "disabled": False},
                        {"key": {"section": "run", "name": ""}, "op": "=", "value": "", "disabled": True},
                    ],
                    "disabled": False,
                },
            ],
        }
        tree = filters_v2_to_filters_tree(v2)
        assert tree.op == "OR"
        and_bucket = tree.filters[0]
        assert and_bucket.op == "AND"
        assert len(and_bucket.filters) == 3
        assert and_bucket.filters[0].value == "finished"
        assert and_bucket.filters[1].value == 0.001
        assert and_bucket.filters[2].value == "CW-JHWYNJMYJF-L"

        expr_str = filters_to_expr(tree)
        assert "and" in expr_str.lower()
        assert "finished" in expr_str


class TestV2RoundTrip:
    """Test that Filters tree -> v2 dict -> Filters tree round-trips correctly."""

    def test_simple_and_round_trip(self):
        from wandb_workspaces.expr import (
            Filters,
            Key,
            filters_tree_to_v2,
            filters_v2_to_filters_tree,
        )

        tree = Filters(op="OR", filters=[
            Filters(op="AND", filters=[
                Filters(op="=", key=Key(section="config", name="lr"), value=0.01),
                Filters(op="=", key=Key(section="run", name="state"), value="finished"),
            ])
        ])
        v2 = filters_tree_to_v2(tree)
        assert v2["filterFormat"] == "filterV2"
        assert len(v2["filters"]) == 2
        assert "connector" not in v2["filters"][0]
        assert v2["filters"][1]["connector"] == "AND"

        round_tripped = filters_v2_to_filters_tree(v2)
        assert round_tripped.op == "OR"
        assert len(round_tripped.filters) == 1
        assert round_tripped.filters[0].op == "AND"
        assert len(round_tripped.filters[0].filters) == 2

    def test_or_round_trip(self):
        from wandb_workspaces.expr import (
            Filters,
            Key,
            filters_tree_to_v2,
            filters_v2_to_filters_tree,
        )

        tree = Filters(op="OR", filters=[
            Filters(op="AND", filters=[
                Filters(op="=", key=Key(section="config", name="lr"), value=0.01),
                Filters(op="=", key=Key(section="run", name="state"), value="finished"),
            ]),
            Filters(op="AND", filters=[
                Filters(op="=", key=Key(section="config", name="lr"), value=0.1),
            ]),
        ])
        v2 = filters_tree_to_v2(tree)
        assert v2["filterFormat"] == "filterV2"
        assert len(v2["filters"]) == 3
        assert "connector" not in v2["filters"][0]
        assert v2["filters"][1]["connector"] == "AND"
        assert v2["filters"][2]["connector"] == "OR"

        round_tripped = filters_v2_to_filters_tree(v2)
        assert round_tripped.op == "OR"
        assert len(round_tripped.filters) == 2
        assert round_tripped.filters[0].op == "AND"
        assert len(round_tripped.filters[0].filters) == 2
        assert round_tripped.filters[1].op == "AND"
        assert round_tripped.filters[1].filters[0].value == 0.1

    def test_empty_round_trip(self):
        from wandb_workspaces.expr import (
            Filters,
            filters_tree_to_v2,
        )

        tree = Filters(op="OR", filters=[Filters(op="AND", filters=[])])
        v2 = filters_tree_to_v2(tree)
        assert v2["filterFormat"] == "filterV2"
        assert v2["filters"] == []

    def test_string_to_v2_round_trip(self):
        """Full pipeline: string -> tree -> v2 -> tree -> string."""
        from wandb_workspaces.expr import (
            expr_to_filters,
            filters_to_expr,
            filters_tree_to_v2,
            filters_v2_to_filters_tree,
        )

        original = "Metric('State') == 'finished' and Config('lr') == 0.01 or Config('lr') == 0.1"
        tree1 = expr_to_filters(original)
        v2 = filters_tree_to_v2(tree1)
        tree2 = filters_v2_to_filters_tree(v2)
        result = filters_to_expr(tree2)
        tree3 = expr_to_filters(result)
        assert len(tree3.filters) == 2
        assert tree3.filters[0].op == "AND"
        assert tree3.filters[1].op == "AND"

    def test_v2_dict_to_tree_to_v2_preserves_structure(self):
        """v2 dict -> tree -> v2 dict should preserve filter values and connectors."""
        from wandb_workspaces.expr import (
            filters_tree_to_v2,
            filters_v2_to_filters_tree,
        )

        original_v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished"},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01, "connector": "AND"},
                {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.1, "connector": "OR"},
            ],
        }
        tree = filters_v2_to_filters_tree(original_v2)
        result_v2 = filters_tree_to_v2(tree)

        assert result_v2["filterFormat"] == "filterV2"
        items = result_v2["filters"]
        assert len(items) == 3
        assert items[0]["value"] == "finished"
        assert "connector" not in items[0]
        assert items[1]["value"] == 0.01
        assert items[1]["connector"] == "AND"
        assert items[2]["value"] == 0.1
        assert items[2]["connector"] == "OR"

    def test_nested_group_round_trip(self):
        """v2 with nested group -> tree -> v2 should preserve the group."""
        from wandb_workspaces.expr import (
            filters_tree_to_v2,
            filters_v2_to_filters_tree,
        )

        original_v2 = {
            "filterFormat": "filterV2",
            "filters": [
                {"op": "=", "key": {"section": "run", "name": "state"}, "value": "finished"},
                {
                    "connector": "AND",
                    "filters": [
                        {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.01},
                        {"op": "=", "key": {"section": "config", "name": "lr"}, "value": 0.1, "connector": "OR"},
                    ],
                },
            ],
        }
        tree = filters_v2_to_filters_tree(original_v2)
        result_v2 = filters_tree_to_v2(tree)

        assert result_v2["filterFormat"] == "filterV2"
        items = result_v2["filters"]
        assert items[0]["value"] == "finished"
        has_group = any("filters" in item for item in items)
        assert has_group, "Nested group should be preserved in round-trip"
