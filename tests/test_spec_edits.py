"""Applying a workspace's edits onto the spec it was loaded from."""

from wandb_workspaces.workspaces._spec_edits import apply_edits, value_at

LOADED = {
    "section": {
        "version": 7,
        "runSets": [{"id": "rs1", "pageSize": 50, "search": {"query": ""}}],
        "customRunColors": {"run-a": "#f00", "run-b": "#0f0"},
    }
}


def test_no_edit_returns_the_loaded_spec_as_is():
    before = {"section": {"runSets": [{"id": "rs1", "search": {"query": ""}}]}}
    assert apply_edits(LOADED, before, before) is LOADED


def test_an_edited_scalar_changes_only_its_path():
    before = {"section": {"runSets": [{"id": "rs1", "search": {"query": ""}}]}}
    after = {"section": {"runSets": [{"id": "rs1", "search": {"query": "loss"}}]}}

    merged = apply_edits(LOADED, before, after)

    assert merged["section"]["runSets"][0]["search"] == {"query": "loss"}
    assert merged["section"]["runSets"][0]["pageSize"] == 50
    assert merged["section"]["version"] == 7


def test_a_default_the_sdk_fills_in_is_not_added_unless_changed():
    """The SDK rebuilds `pageSize: 10` for a spec that has none. Unchanged,
    it stays absent; changed, it is written."""
    loaded = {"runFeed": {"columnOrder": []}}
    before = {"runFeed": {"columnOrder": [], "pageSize": 10}}

    same = apply_edits(
        loaded, before, {"runFeed": {"columnOrder": ["a"], "pageSize": 10}}
    )
    assert same == {"runFeed": {"columnOrder": ["a"]}}

    changed = apply_edits(
        loaded, before, {"runFeed": {"columnOrder": [], "pageSize": 20}}
    )
    assert changed == {"runFeed": {"columnOrder": [], "pageSize": 20}}


def test_a_key_the_edit_removes_is_removed():
    before = {"customRunColors": {"run-a": "#f00", "run-b": "#0f0"}}
    after = {"customRunColors": {"run-b": "#0f0"}}

    merged = apply_edits(LOADED["section"], before, after)

    assert merged["customRunColors"] == {"run-b": "#0f0"}


def test_a_key_the_edit_adds_is_added():
    before = {"customRunColors": {"run-a": "#f00", "run-b": "#0f0"}}
    after = {"customRunColors": {"run-a": "#f00", "run-b": "#0f0", "run-c": "#00f"}}

    merged = apply_edits(LOADED["section"], before, after)

    assert merged["customRunColors"]["run-c"] == "#00f"


def test_list_items_are_matched_by_id_so_a_move_keeps_unmodeled_fields():
    loaded = [
        {"__id__": "a", "name": "A", "sorted": 1, "unknown": True},
        {"__id__": "b", "name": "B", "sorted": 0},
    ]
    before = [{"__id__": "a", "name": "A"}, {"__id__": "b", "name": "B"}]
    after = [{"__id__": "b", "name": "B"}, {"__id__": "a", "name": "A renamed"}]

    merged = apply_edits(loaded, before, after)

    assert merged == [
        {"__id__": "b", "name": "B", "sorted": 0},
        {"__id__": "a", "name": "A renamed", "sorted": 1, "unknown": True},
    ]


def test_loaded_items_pair_with_rebuilt_items_by_id_when_the_rebuild_reordered_them():
    """The rebuild moves Hidden Panels last, so `before` can be a permutation
    of `loaded`: an edit must still land on the item with the same id."""
    loaded = [
        {"__id__": "hp", "name": "Hidden Panels", "isOpen": False, "sorted": 0},
        {"__id__": "a", "name": "A", "isOpen": True, "extra": 1},
    ]
    before = [
        {"__id__": "a", "name": "A", "isOpen": True},
        {"__id__": "hp", "name": "Hidden Panels", "isOpen": False},
    ]
    after = [
        {"__id__": "a", "name": "A", "isOpen": False},
        {"__id__": "hp", "name": "Hidden Panels", "isOpen": False},
    ]

    merged = apply_edits(loaded, before, after)

    assert merged == [
        {"__id__": "a", "name": "A", "isOpen": False, "extra": 1},
        {"__id__": "hp", "name": "Hidden Panels", "isOpen": False, "sorted": 0},
    ]


def test_items_the_rebuild_gave_an_id_pair_in_order_after_a_reorder():
    """A stored section without `__id__` gets one in the rebuild, so it cannot
    pair by id; with Hidden Panels moved last it is no longer at its index
    either. It pairs with the loaded item left over."""
    loaded = [
        {"__id__": "a", "name": "A"},
        {"__id__": "hp", "name": "Hidden Panels", "sorted": 0},
        {"name": "C", "isOpen": False, "unmodeled": True},
    ]
    before = [
        {"__id__": "a", "name": "A"},
        {"__id__": "gen", "name": "C", "isOpen": False},
        {"__id__": "hp", "name": "Hidden Panels"},
    ]
    after = [
        {"__id__": "a", "name": "A"},
        {"__id__": "gen", "name": "C", "isOpen": True},
        {"__id__": "hp", "name": "Hidden Panels"},
    ]

    merged = apply_edits(loaded, before, after)

    assert merged == [
        {"__id__": "a", "name": "A"},
        {"name": "C", "isOpen": True, "unmodeled": True},
        {"__id__": "hp", "name": "Hidden Panels", "sorted": 0},
    ]


def test_a_new_list_item_is_added_and_a_removed_one_dropped():
    loaded = [{"__id__": "a", "extra": 1}, {"__id__": "b", "extra": 2}]
    before = [{"__id__": "a"}, {"__id__": "b"}]
    after = [{"__id__": "b"}, {"__id__": "c", "name": "new"}]

    merged = apply_edits(loaded, before, after)

    assert merged == [{"__id__": "b", "extra": 2}, {"__id__": "c", "name": "new"}]


def test_items_without_ids_match_by_equality_then_position():
    loaded = [{"key": "x", "extra": 1}, {"key": "y", "extra": 2}]
    before = [{"key": "x"}, {"key": "y"}]
    after = [{"key": "x"}, {"key": "z"}]

    merged = apply_edits(loaded, before, after)

    assert merged == [{"key": "x", "extra": 1}, {"key": "z", "extra": 2}]


def test_a_type_change_takes_the_edit():
    assert apply_edits({"a": [1]}, {"a": [1]}, {"a": 1}) == {"a": 1}
    assert apply_edits({"a": 1}, {"a": 1}, {"a": {"b": 2}}) == {"a": {"b": 2}}


def test_value_at_skips_parts_that_are_not_keys():
    """A validation error's location names the union member a panel matched
    (`Media Browser`); the spec has no such key."""
    spec = {"panels": [{"viewType": "Media Browser", "config": {"x": 1}}]}

    assert value_at(spec, ("panels", 0, "Media Browser", "config", "x")) == (True, 1)
    assert value_at(spec, ("panels", 0, "config", "missing")) == (False, None)
    assert value_at(spec, ("panels", 3)) == (False, None)
